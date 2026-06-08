// Supabase Edge Function: live-sync
// Receives batches of local events from FenceSpace Live clients.
// Validates auth, checks device registration, writes event log,
// applies events to live tables, fans out push notifications.
// Returns { acked: [{id}], rejected: [{id, reason}] }

import { createClient } from 'jsr:@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface IncomingEvent {
  id: string
  tournamentId: string
  deviceId: string
  sequence: number
  type: string
  payload: Record<string, unknown>
  stripId: string | null
  actorId: string
  createdAt: number  // milliseconds
}

interface SyncAck { id: string }
interface SyncReject { id: string; reason: string }

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )

  // Validate JWT and extract user
  const authHeader = req.headers.get('Authorization')
  if (!authHeader) {
    return new Response(JSON.stringify({ error: 'missing authorization' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }

  const token = authHeader.replace('Bearer ', '')
  const { data: { user }, error: authError } = await supabase.auth.getUser(token)
  if (authError || !user) {
    return new Response(JSON.stringify({ error: 'unauthorized' }), {
      status: 401,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }

  let body: { events: IncomingEvent[] }
  try {
    body = await req.json()
  } catch {
    return new Response(JSON.stringify({ error: 'invalid json' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }

  const { events } = body
  if (!Array.isArray(events) || events.length === 0) {
    return new Response(JSON.stringify({ acked: [], rejected: [] }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }

  const acked: SyncAck[] = []
  const rejected: SyncReject[] = []

  // Group events by deviceId to validate each device once
  const deviceIds = [...new Set(events.map(e => e.deviceId))]
  const validDevices = new Set<string>()

  for (const deviceId of deviceIds) {
    const { data: device, error } = await supabase
      .from('fs_live_devices')
      .select('id, user_id, tournament_id')
      .eq('id', deviceId)
      .eq('user_id', user.id)
      .maybeSingle()

    if (!error && device) {
      validDevices.add(deviceId)
      // Update last_seen_at (fire-and-forget, non-critical)
      supabase
        .from('fs_live_devices')
        .update({ last_seen_at: new Date().toISOString() })
        .eq('id', deviceId)
        .then(() => {})
    }
  }

  // Process each event
  for (const event of events) {
    // Validate device ownership
    if (!validDevices.has(event.deviceId)) {
      rejected.push({ id: event.id, reason: 'device_not_registered' })
      continue
    }

    // Validate event type is known
    if (!isKnownEventType(event.type)) {
      rejected.push({ id: event.id, reason: `unknown_event_type:${event.type}` })
      continue
    }

    // Write to event log — ON CONFLICT DO NOTHING provides idempotency
    // PK is (device_id, sequence), so duplicate submissions are silently skipped
    const { error: logError } = await supabase
      .from('fs_live_event_log')
      .upsert({
        id:            event.id,
        tournament_id: event.tournamentId,
        device_id:     event.deviceId,
        sequence:      event.sequence,
        type:          event.type,
        payload:       event.payload,
        strip_id:      event.stripId,
        actor_id:      event.actorId,
        created_at:    new Date(event.createdAt).toISOString(),
      }, {
        onConflict: 'device_id,sequence',
        ignoreDuplicates: true,
      })

    if (logError) {
      rejected.push({ id: event.id, reason: `log_write_failed:${logError.message}` })
      continue
    }

    // Apply event to live tables
    const applyError = await applyEvent(supabase, event)
    if (applyError) {
      // Log write succeeded (audit trail preserved), but application failed
      // Return as rejected so client can surface to TD
      rejected.push({ id: event.id, reason: `apply_failed:${applyError}` })
      continue
    }

    // Fan-out push notifications for strip-call events
    if (event.type === 'FENCER_STRIP_CALLED') {
      fanOutStripCallNotification(supabase, event).catch(err => {
        console.error('[live-sync] push fan-out error:', err)
      })
    }

    acked.push({ id: event.id })
  }

  return new Response(JSON.stringify({ acked, rejected }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
})

// Apply a single event to the appropriate live table row(s)
async function applyEvent(
  supabase: ReturnType<typeof createClient>,
  event: IncomingEvent,
): Promise<string | null> {
  const p = event.payload

  try {
    switch (event.type) {
      case 'TOUCH_SCORED':
      case 'TOUCH_CANCELLED': {
        const table = p.boutType === 'de' ? 'fs_live_de_bouts' : 'fs_live_pool_bouts'
        const { error } = await supabase
          .from(table)
          .update({ score_a: p.newScoreA, score_b: p.newScoreB })
          .eq('id', p.boutId)
        return error?.message ?? null
      }

      case 'CARD_ISSUED': {
        // Append card to the jsonb array — use rpc to avoid race conditions
        const table = p.boutType === 'de' ? 'fs_live_de_bouts' : 'fs_live_pool_bouts'
        const card = { fencer_id: p.fencerId, card: p.card, reason: p.reason ?? null, ts: event.createdAt }
        const { error } = await supabase.rpc('fslive_append_card', {
          p_table: table,
          p_bout_id: p.boutId,
          p_card: card,
        })
        return error?.message ?? null
      }

      case 'CARD_REVOKED': {
        const table = p.boutType === 'de' ? 'fs_live_de_bouts' : 'fs_live_pool_bouts'
        const { error } = await supabase.rpc('fslive_remove_card', {
          p_table: table,
          p_bout_id: p.boutId,
          p_fencer_id: p.fencerId,
          p_card: p.card,
        })
        return error?.message ?? null
      }

      case 'POOL_BOUT_STARTED': {
        const { error } = await supabase
          .from('fs_live_pool_bouts')
          .update({ status: 'active', strip_id: p.stripId, started_at: new Date(event.createdAt).toISOString() })
          .eq('id', p.boutId)
        return error?.message ?? null
      }

      case 'DE_BOUT_STARTED': {
        const { error } = await supabase
          .from('fs_live_de_bouts')
          .update({ status: 'active', strip_id: p.stripId, started_at: new Date(event.createdAt).toISOString() })
          .eq('id', p.boutId)
        return error?.message ?? null
      }

      case 'BOUT_ENDED': {
        const table = p.boutType === 'de' ? 'fs_live_de_bouts' : 'fs_live_pool_bouts'
        const { error } = await supabase
          .from(table)
          .update({
            status:    'complete',
            winner_id: p.winnerId,
            score_a:   p.finalScoreA,
            score_b:   p.finalScoreB,
            ended_at:  new Date(event.createdAt).toISOString(),
          })
          .eq('id', p.boutId)
        return error?.message ?? null
      }

      case 'DE_BOUT_WALKOVER': {
        const { error } = await supabase
          .from('fs_live_de_bouts')
          .update({ status: 'walkover', winner_id: p.winnerId })
          .eq('id', p.boutId)
        return error?.message ?? null
      }

      case 'POOL_COMPLETED': {
        const results = p.results as Array<Record<string, unknown>>
        if (!Array.isArray(results)) return 'pool_completed_missing_results'

        // Upsert all result rows in one call
        const { error } = await supabase
          .from('fs_live_pool_results')
          .upsert(results.map(r => ({
            pool_id:          p.poolId,
            registration_id:  r.registrationId,
            victories:        r.victories,
            bouts:            r.bouts,
            touches_scored:   r.touchesScored,
            touches_received: r.touchesReceived,
            pool_rank:        r.poolRank,
            de_seed:          r.deSeed,
            promoted:         r.promoted,
          })))
        if (error) return error.message

        const { error: poolError } = await supabase
          .from('fs_live_pools')
          .update({ status: 'complete' })
          .eq('id', p.poolId)
        return poolError?.message ?? null
      }

      case 'STRIP_ASSIGNED': {
        // Release any existing active assignment for this strip+event first
        await supabase
          .from('fs_live_strip_assignments')
          .update({ released_at: new Date().toISOString() })
          .eq('strip_id', p.stripId)
          .eq('event_id', p.eventId)
          .is('released_at', null)

        const { error } = await supabase
          .from('fs_live_strip_assignments')
          .insert({ strip_id: p.stripId, referee_id: p.refereeId, event_id: p.eventId })
        return error?.message ?? null
      }

      case 'REFEREE_ROTATED': {
        const now = new Date().toISOString()
        await supabase
          .from('fs_live_strip_assignments')
          .update({ released_at: now })
          .eq('strip_id', p.fromStripId)
          .eq('referee_id', p.refereeId)
          .is('released_at', null)

        const { error } = await supabase
          .from('fs_live_strip_assignments')
          .insert({ strip_id: p.toStripId, referee_id: p.refereeId, event_id: p.eventId })
        return error?.message ?? null
      }

      case 'POOL_GENERATED': {
        // Payload shape: { eventId, poolCount, totalFencers, pools: [...] }
        // Each pool: { poolId, poolNumber, size, assignments: [{registrationId, position}], bouts: [{boutId, positionA, positionB, boutOrder}] }
        // We use the pre-generated UUIDs from the client so these are idempotent.
        type PoolEntry = {
          poolId: string; poolNumber: number; size: number
          assignments: Array<{ registrationId: string; position: number }>
          bouts: Array<{ boutId: string; positionA: number; positionB: number; boutOrder: number }>
        }
        const pools = p.pools as PoolEntry[]
        if (!Array.isArray(pools)) return 'pool_generated_missing_pools'

        // Insert all pool rows in one call
        const { error: poolsErr } = await supabase
          .from('fs_live_pools')
          .upsert(
            pools.map(pool => ({ id: pool.poolId, event_id: p.eventId, pool_number: pool.poolNumber })),
            { onConflict: 'id', ignoreDuplicates: true },
          )
        if (poolsErr) return poolsErr.message

        // Build flat assignment + bout arrays across all pools
        const allAssignments: Array<{ pool_id: string; registration_id: string; position: number }> = []
        const allBouts: Array<{
          id: string; pool_id: string; fencer_a_id: string; fencer_b_id: string; bout_order: number; status: string
        }> = []

        for (const pool of pools) {
          for (const a of pool.assignments) {
            allAssignments.push({ pool_id: pool.poolId, registration_id: a.registrationId, position: a.position })
          }
          // Build position → registrationId map for this pool's bout resolution
          const posMap = new Map<number, string>(pool.assignments.map(a => [a.position, a.registrationId]))
          for (const b of pool.bouts) {
            const fencerA = posMap.get(b.positionA)
            const fencerB = posMap.get(b.positionB)
            if (!fencerA || !fencerB) continue   // defensive: malformed payload
            allBouts.push({
              id:          b.boutId,
              pool_id:     pool.poolId,
              fencer_a_id: fencerA,
              fencer_b_id: fencerB,
              bout_order:  b.boutOrder,
              status:      'scheduled',
            })
          }
        }

        const { error: assignErr } = await supabase
          .from('fs_live_pool_assignments')
          .upsert(allAssignments, { onConflict: 'pool_id,registration_id', ignoreDuplicates: true })
        if (assignErr) return assignErr.message

        const { error: boutsErr } = await supabase
          .from('fs_live_pool_bouts')
          .upsert(allBouts, { onConflict: 'id', ignoreDuplicates: true })
        return boutsErr?.message ?? null
      }

      case 'DE_BRACKET_SEEDED': {
        // Payload shape: { eventId, bracketId, tableauSize, promotedCount, byeCount, totalRounds, seedings, bouts }
        // Each bout: { boutId, round, tableauPos, fencerAId, fencerBId, status }
        const { error: bracketErr } = await supabase
          .from('fs_live_de_brackets')
          .upsert(
            { id: p.bracketId, event_id: p.eventId, tableau_size: p.tableauSize },
            { onConflict: 'id', ignoreDuplicates: true },
          )
        if (bracketErr) return bracketErr.message

        type DEBoutEntry = {
          boutId: string; round: number; tableauPos: number
          fencerAId: string | null; fencerBId: string | null
          status: 'scheduled' | 'bye'
        }
        const debouts = p.bouts as DEBoutEntry[]
        if (!Array.isArray(debouts)) return 'de_bracket_seeded_missing_bouts'

        const { error: deboutsErr } = await supabase
          .from('fs_live_de_bouts')
          .upsert(
            debouts.map(b => ({
              id:          b.boutId,
              bracket_id:  p.bracketId,
              round:       b.round,
              tableau_pos: b.tableauPos,
              fencer_a_id: b.fencerAId,
              fencer_b_id: b.fencerBId,
              status:      b.status,
            })),
            { onConflict: 'id', ignoreDuplicates: true },
          )
        return deboutsErr?.message ?? null
      }

      // Events that only write to the event log (no secondary table mutation needed)
      case 'TOURNAMENT_CREATED':
      case 'EVENT_CONFIGURED':
      case 'REGISTRATION_ADDED':
      case 'REGISTRATION_SCRATCHED':
      case 'FENCER_STRIP_CALLED':
      case 'PROTEST_OPENED':
      case 'PROTEST_RESOLVED':
        return null

      default:
        return null
    }
  } catch (err) {
    return err instanceof Error ? err.message : String(err)
  }
}

// Fan out Web Push notifications to all spectators following the called fencer
async function fanOutStripCallNotification(
  supabase: ReturnType<typeof createClient>,
  event: IncomingEvent,
): Promise<void> {
  const p = event.payload as Record<string, unknown>
  const registrationId = p.registrationId as string

  // Get registration display name for the notification body
  const { data: reg } = await supabase
    .from('fs_live_registrations')
    .select('display_name, fencer_id, claim_token')
    .eq('id', registrationId)
    .maybeSingle()

  if (!reg) return

  // Find all followers: by registration_id directly, or by linked fencer_id
  const { data: follows } = await supabase
    .from('fs_live_spectator_follows')
    .select('spectator_id')
    .or(`registration_id.eq.${registrationId}${reg.fencer_id ? `,fencer_id.eq.${reg.fencer_id}` : ''}`)
    .eq('notify_strip_call', true)

  if (!follows || follows.length === 0) return

  const spectatorIds = follows.map(f => f.spectator_id as string)

  // Fetch push subscriptions for all followers in one query
  const { data: subs } = await supabase
    .from('fs_live_push_subscriptions')
    .select('endpoint, p256dh, auth_key, user_id')
    .in('user_id', spectatorIds)

  if (!subs || subs.length === 0) return

  const name = reg.display_name ?? 'Your fencer'
  const stripNumber = p.stripNumber as number
  const title = `${name} called to Strip ${stripNumber}`
  const body = `Head to Strip ${stripNumber} now`

  // Send Web Push via Supabase Edge Function worker (or directly via web-push library)
  // Batched invocation to avoid per-subscription cold starts
  const PUSH_FUNCTION_URL = `${Deno.env.get('SUPABASE_URL')}/functions/v1/send-push`
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!

  await fetch(PUSH_FUNCTION_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${serviceKey}`,
    },
    body: JSON.stringify({
      subscriptions: subs,
      notification: { title, body, tag: `strip-call-${registrationId}` },
    }),
  })
}

const KNOWN_EVENT_TYPES = new Set([
  'TOURNAMENT_CREATED', 'EVENT_CONFIGURED',
  'REGISTRATION_ADDED', 'REGISTRATION_SCRATCHED',
  'POOL_GENERATED', 'POOL_BOUT_STARTED',
  'TOUCH_SCORED', 'TOUCH_CANCELLED',
  'CARD_ISSUED', 'CARD_REVOKED',
  'BOUT_ENDED', 'POOL_COMPLETED',
  'DE_BRACKET_SEEDED', 'DE_BOUT_STARTED', 'DE_BOUT_ENDED', 'DE_BOUT_WALKOVER',
  'STRIP_ASSIGNED', 'REFEREE_ROTATED', 'FENCER_STRIP_CALLED',
  'PROTEST_OPENED', 'PROTEST_RESOLVED',
])

function isKnownEventType(type: string): boolean {
  return KNOWN_EVENT_TYPES.has(type)
}
