CREATE TABLE IF NOT EXISTS public.fs_trivia_questions (
    id text PRIMARY KEY,
    question_type text NOT NULL,
    fencer_id uuid REFERENCES public.fs_fencers(id) ON DELETE CASCADE,
    question text NOT NULL,
    answer text NOT NULL,
    options jsonb NOT NULL CHECK (
        jsonb_typeof(options) = 'array'
        AND jsonb_array_length(options) >= 2
    ),
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(source_metadata) = 'object'
    ),
    safety_flags jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (
        jsonb_typeof(safety_flags) = 'object'
    ),
    generated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    created_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_fs_trivia_questions_fencer_id
    ON public.fs_trivia_questions(fencer_id)
    WHERE fencer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fs_trivia_questions_type
    ON public.fs_trivia_questions(question_type);

ALTER TABLE public.fs_trivia_questions ENABLE ROW LEVEL SECURITY;
