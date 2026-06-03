CREATE TABLE IF NOT EXISTS public.fs_country_codes (
    alpha3 text PRIMARY KEY,
    alpha2 text,
    name text NOT NULL,
    region text,
    continent text,
    flag_emoji text,
    olympic_code text,
    fie_code text,
    aliases text[] NOT NULL DEFAULT '{}'::text[],
    latitude numeric,
    longitude numeric,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fs_country_codes_alpha3_format CHECK (alpha3 ~ '^[A-Z0-9]{3}$'),
    CONSTRAINT fs_country_codes_alpha2_format CHECK (alpha2 IS NULL OR alpha2 ~ '^[A-Z]{2}$')
);

ALTER TABLE public.fs_country_codes ENABLE ROW LEVEL SECURITY;

CREATE UNIQUE INDEX IF NOT EXISTS fs_country_codes_alpha2_idx
    ON public.fs_country_codes (alpha2)
    WHERE alpha2 IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS fs_country_codes_olympic_code_idx
    ON public.fs_country_codes (olympic_code)
    WHERE olympic_code IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS fs_country_codes_fie_code_idx
    ON public.fs_country_codes (fie_code)
    WHERE fie_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_country_codes_name_idx
    ON public.fs_country_codes (lower(name));

CREATE INDEX IF NOT EXISTS fs_country_codes_aliases_idx
    ON public.fs_country_codes USING gin (aliases);

CREATE OR REPLACE FUNCTION public.fs_country_codes_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'fs_country_codes_set_updated_at'
          AND tgrelid = 'public.fs_country_codes'::regclass
    ) THEN
        CREATE TRIGGER fs_country_codes_set_updated_at
        BEFORE UPDATE ON public.fs_country_codes
        FOR EACH ROW
        EXECUTE FUNCTION public.fs_country_codes_touch_updated_at();
    END IF;
END;
$$;

WITH seed AS (
    SELECT *
    FROM jsonb_to_recordset($country_codes$
[
  {"alpha3":"ABW","alpha2":"AW","name":"Aruba","region":"Caribbean","continent":"Americas","olympic_code":"ARU","fie_code":"ARU","aliases":["ARUBA"],"latitude":12.5211,"longitude":-69.9683},
  {"alpha3":"AGO","alpha2":"AO","name":"Angola","region":"Middle Africa","continent":"Africa","olympic_code":"ANG","fie_code":"ANG","aliases":["ANGOLA"],"latitude":-11.2027,"longitude":17.8739},
  {"alpha3":"AHO","alpha2":null,"name":"Netherlands Antilles","region":"Caribbean","continent":"Americas","olympic_code":"AHO","fie_code":null,"aliases":["ANTILLAS NEERLANDESAS","NETHERLANDS ANTILLES"],"latitude":12.2261,"longitude":-69.0601},
  {"alpha3":"AIN","alpha2":null,"name":"Individual Neutral Athletes","region":"Neutral","continent":"International","olympic_code":"AIN","fie_code":"AIN","aliases":["_AIN","AIN_","INDIVIDUAL NEUTRAL ATHLETES","NEUTRAL ATHLETES"],"latitude":null,"longitude":null},
  {"alpha3":"ARE","alpha2":"AE","name":"United Arab Emirates","region":"Western Asia","continent":"Asia","olympic_code":"UAE","fie_code":"UAE","aliases":["UAE","UNITED ARAB EMIRATES"],"latitude":23.4241,"longitude":53.8478},
  {"alpha3":"ARG","alpha2":"AR","name":"Argentina","region":"South America","continent":"Americas","olympic_code":"ARG","fie_code":"ARG","aliases":["ARGENTINA"],"latitude":-38.4161,"longitude":-63.6167},
  {"alpha3":"ARM","alpha2":"AM","name":"Armenia","region":"Western Asia","continent":"Asia","olympic_code":"ARM","fie_code":"ARM","aliases":["ARMENIA"],"latitude":40.0691,"longitude":45.0382},
  {"alpha3":"AUS","alpha2":"AU","name":"Australia","region":"Australia and New Zealand","continent":"Oceania","olympic_code":"AUS","fie_code":"AUS","aliases":["AUST","AUSTRALIA"],"latitude":-25.2744,"longitude":133.7751},
  {"alpha3":"AUT","alpha2":"AT","name":"Austria","region":"Western Europe","continent":"Europe","olympic_code":"AUT","fie_code":"AUT","aliases":["AUSTRIA"],"latitude":47.5162,"longitude":14.5501},
  {"alpha3":"AZE","alpha2":"AZ","name":"Azerbaijan","region":"Western Asia","continent":"Asia","olympic_code":"AZE","fie_code":"AZE","aliases":["AZERBAIJAN"],"latitude":40.1431,"longitude":47.5769},
  {"alpha3":"BEL","alpha2":"BE","name":"Belgium","region":"Western Europe","continent":"Europe","olympic_code":"BEL","fie_code":"BEL","aliases":["BELGIUM"],"latitude":50.5039,"longitude":4.4699},
  {"alpha3":"BHS","alpha2":"BS","name":"Bahamas","region":"Caribbean","continent":"Americas","olympic_code":"BAH","fie_code":"BAH","aliases":["BAHAMAS"],"latitude":25.0343,"longitude":-77.3963},
  {"alpha3":"BMU","alpha2":"BM","name":"Bermuda","region":"Northern America","continent":"Americas","olympic_code":"BER","fie_code":"BER","aliases":["BERMUDA"],"latitude":32.3078,"longitude":-64.7505},
  {"alpha3":"BOL","alpha2":"BO","name":"Bolivia","region":"South America","continent":"Americas","olympic_code":"BOL","fie_code":"BOL","aliases":["BOLIVIA"],"latitude":-16.2902,"longitude":-63.5887},
  {"alpha3":"BRA","alpha2":"BR","name":"Brazil","region":"South America","continent":"Americas","olympic_code":"BRA","fie_code":"BRA","aliases":["BRASIL","BRAZIL"],"latitude":-14.235,"longitude":-51.9253},
  {"alpha3":"BRB","alpha2":"BB","name":"Barbados","region":"Caribbean","continent":"Americas","olympic_code":"BAR","fie_code":"BAR","aliases":["BARBADOS"],"latitude":13.1939,"longitude":-59.5432},
  {"alpha3":"BUL","alpha2":"BG","name":"Bulgaria","region":"Eastern Europe","continent":"Europe","olympic_code":"BUL","fie_code":"BUL","aliases":["BULGARIA"],"latitude":42.7339,"longitude":25.4858},
  {"alpha3":"CAN","alpha2":"CA","name":"Canada","region":"Northern America","continent":"Americas","olympic_code":"CAN","fie_code":"CAN","aliases":["CANADA"],"latitude":56.1304,"longitude":-106.3468},
  {"alpha3":"CCS","alpha2":null,"name":"Centro Caribe Sports","region":"Caribbean","continent":"Americas","olympic_code":null,"fie_code":null,"aliases":["CENTRO CARIBE SPORTS"],"latitude":null,"longitude":null},
  {"alpha3":"CHE","alpha2":"CH","name":"Switzerland","region":"Western Europe","continent":"Europe","olympic_code":"SUI","fie_code":"SUI","aliases":["SWITZERLAND"],"latitude":46.8182,"longitude":8.2275},
  {"alpha3":"CHL","alpha2":"CL","name":"Chile","region":"South America","continent":"Americas","olympic_code":"CHI","fie_code":"CHI","aliases":["CHILE"],"latitude":-35.6751,"longitude":-71.543},
  {"alpha3":"CHN","alpha2":"CN","name":"China","region":"Eastern Asia","continent":"Asia","olympic_code":"CHN","fie_code":"CHN","aliases":["CHINA","PEOPLE'S REPUBLIC OF CHINA"],"latitude":35.8617,"longitude":104.1954},
  {"alpha3":"CIV","alpha2":"CI","name":"Cote d'Ivoire","region":"Western Africa","continent":"Africa","olympic_code":"CIV","fie_code":"CIV","aliases":["COTE D'IVOIRE","COTE DIVOIRE","IVORY COAST"],"latitude":7.54,"longitude":-5.5471},
  {"alpha3":"COD","alpha2":"CD","name":"Democratic Republic of the Congo","region":"Middle Africa","continent":"Africa","olympic_code":"COD","fie_code":"COD","aliases":["DEMOCRATIC REPUBLIC OF THE CONGO","DR CONGO"],"latitude":-4.0383,"longitude":21.7587},
  {"alpha3":"COL","alpha2":"CO","name":"Colombia","region":"South America","continent":"Americas","olympic_code":"COL","fie_code":"COL","aliases":["COLOMBIA"],"latitude":4.5709,"longitude":-74.2973},
  {"alpha3":"CRC","alpha2":"CR","name":"Costa Rica","region":"Central America","continent":"Americas","olympic_code":"CRC","fie_code":"CRC","aliases":["COSTA RICA"],"latitude":9.7489,"longitude":-83.7534},
  {"alpha3":"CRO","alpha2":"HR","name":"Croatia","region":"Southern Europe","continent":"Europe","olympic_code":"CRO","fie_code":"CRO","aliases":["CROATIA"],"latitude":45.1,"longitude":15.2},
  {"alpha3":"CUB","alpha2":"CU","name":"Cuba","region":"Caribbean","continent":"Americas","olympic_code":"CUB","fie_code":"CUB","aliases":["CUBA"],"latitude":21.5218,"longitude":-77.7812},
  {"alpha3":"CUW","alpha2":"CW","name":"Curacao","region":"Caribbean","continent":"Americas","olympic_code":"CUR","fie_code":"CUR","aliases":["CURACAO","CURAZAO"],"latitude":12.1696,"longitude":-68.99},
  {"alpha3":"CYP","alpha2":"CY","name":"Cyprus","region":"Western Asia","continent":"Asia","olympic_code":"CYP","fie_code":"CYP","aliases":["CYPRUS"],"latitude":35.1264,"longitude":33.4299},
  {"alpha3":"CZE","alpha2":"CZ","name":"Czech Republic","region":"Eastern Europe","continent":"Europe","olympic_code":"CZE","fie_code":"CZE","aliases":["CZECH REPUBLIC","CZECHIA"],"latitude":49.8175,"longitude":15.473},
  {"alpha3":"DEU","alpha2":"DE","name":"Germany","region":"Western Europe","continent":"Europe","olympic_code":"GER","fie_code":"GER","aliases":["GERMANY"],"latitude":51.1657,"longitude":10.4515},
  {"alpha3":"DEN","alpha2":"DK","name":"Denmark","region":"Northern Europe","continent":"Europe","olympic_code":"DEN","fie_code":"DEN","aliases":["DENMARK"],"latitude":56.2639,"longitude":9.5018},
  {"alpha3":"DOM","alpha2":"DO","name":"Dominican Republic","region":"Caribbean","continent":"Americas","olympic_code":"DOM","fie_code":"DOM","aliases":["DOMINICAN REPUBLIC","REPUBLICA DOMINICANA"],"latitude":18.7357,"longitude":-70.1627},
  {"alpha3":"DZA","alpha2":"DZ","name":"Algeria","region":"Northern Africa","continent":"Africa","olympic_code":"ALG","fie_code":"ALG","aliases":["ALGERIA"],"latitude":28.0339,"longitude":1.6596},
  {"alpha3":"ECU","alpha2":"EC","name":"Ecuador","region":"South America","continent":"Americas","olympic_code":"ECU","fie_code":"ECU","aliases":["ECUADOR"],"latitude":-1.8312,"longitude":-78.1834},
  {"alpha3":"EGY","alpha2":"EG","name":"Egypt","region":"Northern Africa","continent":"Africa","olympic_code":"EGY","fie_code":"EGY","aliases":["EGYPT"],"latitude":26.8206,"longitude":30.8025},
  {"alpha3":"ENG","alpha2":null,"name":"England","region":"Commonwealth","continent":"Europe","olympic_code":null,"fie_code":null,"aliases":["ENGLAND"],"latitude":52.3555,"longitude":-1.1743},
  {"alpha3":"ESP","alpha2":"ES","name":"Spain","region":"Southern Europe","continent":"Europe","olympic_code":"ESP","fie_code":"ESP","aliases":["SPAIN"],"latitude":40.4637,"longitude":-3.7492},
  {"alpha3":"EST","alpha2":"EE","name":"Estonia","region":"Northern Europe","continent":"Europe","olympic_code":"EST","fie_code":"EST","aliases":["ESTONIA"],"latitude":58.5953,"longitude":25.0136},
  {"alpha3":"FIE","alpha2":null,"name":"FIE","region":"International","continent":"International","olympic_code":null,"fie_code":"FIE","aliases":["FEDERATION INTERNATIONALE D'ESCRIME","INTERNATIONAL FENCING FEDERATION"],"latitude":null,"longitude":null},
  {"alpha3":"FIN","alpha2":"FI","name":"Finland","region":"Northern Europe","continent":"Europe","olympic_code":"FIN","fie_code":"FIN","aliases":["FINLAND"],"latitude":61.9241,"longitude":25.7482},
  {"alpha3":"FRA","alpha2":"FR","name":"France","region":"Western Europe","continent":"Europe","olympic_code":"FRA","fie_code":"FRA","aliases":["FRANCE"],"latitude":46.2276,"longitude":2.2137},
  {"alpha3":"GBR","alpha2":"GB","name":"Great Britain","region":"Northern Europe","continent":"Europe","olympic_code":"GBR","fie_code":"GBR","aliases":["GB","GREAT BRITAIN","BRITAIN","UNITED KINGDOM","UK"],"latitude":55.3781,"longitude":-3.436},
  {"alpha3":"GEO","alpha2":"GE","name":"Georgia","region":"Western Asia","continent":"Asia","olympic_code":"GEO","fie_code":"GEO","aliases":["GEORGIA"],"latitude":42.3154,"longitude":43.3569},
  {"alpha3":"GHA","alpha2":"GH","name":"Ghana","region":"Western Africa","continent":"Africa","olympic_code":"GHA","fie_code":"GHA","aliases":["GHANA"],"latitude":7.9465,"longitude":-1.0232},
  {"alpha3":"GRC","alpha2":"GR","name":"Greece","region":"Southern Europe","continent":"Europe","olympic_code":"GRE","fie_code":"GRE","aliases":["GREECE"],"latitude":39.0742,"longitude":21.8243},
  {"alpha3":"GTM","alpha2":"GT","name":"Guatemala","region":"Central America","continent":"Americas","olympic_code":"GUA","fie_code":"GUA","aliases":["GUATEMALA"],"latitude":15.7835,"longitude":-90.2308},
  {"alpha3":"GGY","alpha2":"GG","name":"Guernsey","region":"Commonwealth","continent":"Europe","olympic_code":"GUE","fie_code":null,"aliases":["GUERNSEY"],"latitude":49.4657,"longitude":-2.5853},
  {"alpha3":"GUY","alpha2":"GY","name":"Guyana","region":"South America","continent":"Americas","olympic_code":"GUY","fie_code":"GUY","aliases":["GUYANA"],"latitude":4.8604,"longitude":-58.9302},
  {"alpha3":"HKG","alpha2":"HK","name":"Hong Kong","region":"Eastern Asia","continent":"Asia","olympic_code":"HKG","fie_code":"HKG","aliases":["HONG KONG","HONG KONG, CHINA","HONG KONG CHINA"],"latitude":22.3193,"longitude":114.1694},
  {"alpha3":"HUN","alpha2":"HU","name":"Hungary","region":"Eastern Europe","continent":"Europe","olympic_code":"HUN","fie_code":"HUN","aliases":["HUNGARY"],"latitude":47.1625,"longitude":19.5033},
  {"alpha3":"IDN","alpha2":"ID","name":"Indonesia","region":"South-eastern Asia","continent":"Asia","olympic_code":"INA","fie_code":"INA","aliases":["INDONESIA"],"latitude":-0.7893,"longitude":113.9213},
  {"alpha3":"IND","alpha2":"IN","name":"India","region":"Southern Asia","continent":"Asia","olympic_code":"IND","fie_code":"IND","aliases":["INDIA"],"latitude":20.5937,"longitude":78.9629},
  {"alpha3":"IMN","alpha2":"IM","name":"Isle of Man","region":"Commonwealth","continent":"Europe","olympic_code":"IOM","fie_code":null,"aliases":["ISLE OF MAN"],"latitude":54.2361,"longitude":-4.5481},
  {"alpha3":"IRL","alpha2":"IE","name":"Ireland","region":"Northern Europe","continent":"Europe","olympic_code":"IRL","fie_code":"IRL","aliases":["IRELAND"],"latitude":53.1424,"longitude":-7.6921},
  {"alpha3":"IRN","alpha2":"IR","name":"Iran","region":"Southern Asia","continent":"Asia","olympic_code":"IRI","fie_code":"IRI","aliases":["IRAN","ISLAMIC REPUBLIC OF IRAN"],"latitude":32.4279,"longitude":53.688},
  {"alpha3":"IRQ","alpha2":"IQ","name":"Iraq","region":"Western Asia","continent":"Asia","olympic_code":"IRQ","fie_code":"IRQ","aliases":["IRAQ"],"latitude":33.2232,"longitude":43.6793},
  {"alpha3":"ISR","alpha2":"IL","name":"Israel","region":"Western Asia","continent":"Asia","olympic_code":"ISR","fie_code":"ISR","aliases":["ISRAEL"],"latitude":31.0461,"longitude":34.8516},
  {"alpha3":"ITA","alpha2":"IT","name":"Italy","region":"Southern Europe","continent":"Europe","olympic_code":"ITA","fie_code":"ITA","aliases":["ITALY"],"latitude":41.8719,"longitude":12.5674},
  {"alpha3":"JAM","alpha2":"JM","name":"Jamaica","region":"Caribbean","continent":"Americas","olympic_code":"JAM","fie_code":"JAM","aliases":["JAMAICA"],"latitude":18.1096,"longitude":-77.2975},
  {"alpha3":"JEY","alpha2":"JE","name":"Jersey","region":"Commonwealth","continent":"Europe","olympic_code":"JER","fie_code":null,"aliases":["JERSEY"],"latitude":49.2144,"longitude":-2.1313},
  {"alpha3":"JPN","alpha2":"JP","name":"Japan","region":"Eastern Asia","continent":"Asia","olympic_code":"JPN","fie_code":"JPN","aliases":["JAPAN"],"latitude":36.2048,"longitude":138.2529},
  {"alpha3":"KAZ","alpha2":"KZ","name":"Kazakhstan","region":"Central Asia","continent":"Asia","olympic_code":"KAZ","fie_code":"KAZ","aliases":["KAZAKHSTAN"],"latitude":48.0196,"longitude":66.9237},
  {"alpha3":"KGZ","alpha2":"KG","name":"Kyrgyzstan","region":"Central Asia","continent":"Asia","olympic_code":"KGZ","fie_code":"KGZ","aliases":["KYRGYZSTAN"],"latitude":41.2044,"longitude":74.7661},
  {"alpha3":"KOR","alpha2":"KR","name":"South Korea","region":"Eastern Asia","continent":"Asia","olympic_code":"KOR","fie_code":"KOR","aliases":["KOREA","REPUBLIC OF KOREA","SOUTH KOREA"],"latitude":35.9078,"longitude":127.7669},
  {"alpha3":"KOS","alpha2":"XK","name":"Kosovo","region":"Southern Europe","continent":"Europe","olympic_code":"KOS","fie_code":"KOS","aliases":["KOSOVO"],"latitude":42.6026,"longitude":20.903},
  {"alpha3":"KWT","alpha2":"KW","name":"Kuwait","region":"Western Asia","continent":"Asia","olympic_code":"KUW","fie_code":"KUW","aliases":["KUWAIT"],"latitude":29.3117,"longitude":47.4818},
  {"alpha3":"LBN","alpha2":"LB","name":"Lebanon","region":"Western Asia","continent":"Asia","olympic_code":"LBN","fie_code":"LBN","aliases":["LEBANON"],"latitude":33.8547,"longitude":35.8623},
  {"alpha3":"LVA","alpha2":"LV","name":"Latvia","region":"Northern Europe","continent":"Europe","olympic_code":"LAT","fie_code":"LAT","aliases":["LATVIA"],"latitude":56.8796,"longitude":24.6032},
  {"alpha3":"LTU","alpha2":"LT","name":"Lithuania","region":"Northern Europe","continent":"Europe","olympic_code":"LTU","fie_code":"LTU","aliases":["LITHUANIA"],"latitude":55.1694,"longitude":23.8813},
  {"alpha3":"LUX","alpha2":"LU","name":"Luxembourg","region":"Western Europe","continent":"Europe","olympic_code":"LUX","fie_code":"LUX","aliases":["LUXEMBOURG"],"latitude":49.8153,"longitude":6.1296},
  {"alpha3":"LBY","alpha2":"LY","name":"Libya","region":"Northern Africa","continent":"Africa","olympic_code":"LBA","fie_code":"LBA","aliases":["LIBYA"],"latitude":26.3351,"longitude":17.2283},
  {"alpha3":"MAC","alpha2":"MO","name":"Macau","region":"Eastern Asia","continent":"Asia","olympic_code":null,"fie_code":"MAC","aliases":["MACAO","MACAO, CHINA","MACAO CHINA","MACAU"],"latitude":22.1987,"longitude":113.5439},
  {"alpha3":"MAR","alpha2":"MA","name":"Morocco","region":"Northern Africa","continent":"Africa","olympic_code":"MAR","fie_code":"MAR","aliases":["MOROCCO"],"latitude":31.7917,"longitude":-7.0926},
  {"alpha3":"MDA","alpha2":"MD","name":"Moldova","region":"Eastern Europe","continent":"Europe","olympic_code":"MDA","fie_code":"MDA","aliases":["MOLDOVA"],"latitude":47.4116,"longitude":28.3699},
  {"alpha3":"MDG","alpha2":"MG","name":"Madagascar","region":"Eastern Africa","continent":"Africa","olympic_code":"MAD","fie_code":"MAD","aliases":["MADAGASCAR"],"latitude":-18.7669,"longitude":46.8691},
  {"alpha3":"MEX","alpha2":"MX","name":"Mexico","region":"Central America","continent":"Americas","olympic_code":"MEX","fie_code":"MEX","aliases":["MEXICO"],"latitude":23.6345,"longitude":-102.5528},
  {"alpha3":"MLI","alpha2":"ML","name":"Mali","region":"Western Africa","continent":"Africa","olympic_code":"MLI","fie_code":"MLI","aliases":["MALI"],"latitude":17.5707,"longitude":-3.9962},
  {"alpha3":"MNE","alpha2":"ME","name":"Montenegro","region":"Southern Europe","continent":"Europe","olympic_code":"MNE","fie_code":"MNE","aliases":["MONTENEGRO"],"latitude":42.7087,"longitude":19.3744},
  {"alpha3":"MUS","alpha2":"MU","name":"Mauritius","region":"Eastern Africa","continent":"Africa","olympic_code":"MRI","fie_code":"MRI","aliases":["MAURITIUS"],"latitude":-20.3484,"longitude":57.5522},
  {"alpha3":"MYS","alpha2":"MY","name":"Malaysia","region":"South-eastern Asia","continent":"Asia","olympic_code":"MAS","fie_code":"MAS","aliases":["MAL","MALAYSIA"],"latitude":4.2105,"longitude":101.9758},
  {"alpha3":"NAM","alpha2":"NA","name":"Namibia","region":"Southern Africa","continent":"Africa","olympic_code":"NAM","fie_code":"NAM","aliases":["NAMIBIA"],"latitude":-22.9576,"longitude":18.4904},
  {"alpha3":"NIC","alpha2":"NI","name":"Nicaragua","region":"Central America","continent":"Americas","olympic_code":"NCA","fie_code":"NCA","aliases":["NICARAGUA"],"latitude":12.8654,"longitude":-85.2072},
  {"alpha3":"NIR","alpha2":null,"name":"Northern Ireland","region":"Commonwealth","continent":"Europe","olympic_code":null,"fie_code":null,"aliases":["N.IRE","N IRE","NORTHERN IRELAND"],"latitude":54.7877,"longitude":-6.4923},
  {"alpha3":"NLD","alpha2":"NL","name":"Netherlands","region":"Western Europe","continent":"Europe","olympic_code":"NED","fie_code":"NED","aliases":["NETHERLANDS"],"latitude":52.1326,"longitude":5.2913},
  {"alpha3":"NOR","alpha2":"NO","name":"Norway","region":"Northern Europe","continent":"Europe","olympic_code":"NOR","fie_code":"NOR","aliases":["NORWAY"],"latitude":60.472,"longitude":8.4689},
  {"alpha3":"NZL","alpha2":"NZ","name":"New Zealand","region":"Australia and New Zealand","continent":"Oceania","olympic_code":"NZL","fie_code":"NZL","aliases":["NZ","NEW ZEALAND"],"latitude":-40.9006,"longitude":174.886},
  {"alpha3":"PAN","alpha2":"PA","name":"Panama","region":"Central America","continent":"Americas","olympic_code":"PAN","fie_code":"PAN","aliases":["PANAMA"],"latitude":8.538,"longitude":-80.7821},
  {"alpha3":"PER","alpha2":"PE","name":"Peru","region":"South America","continent":"Americas","olympic_code":"PER","fie_code":"PER","aliases":["PERU"],"latitude":-9.19,"longitude":-75.0152},
  {"alpha3":"PHL","alpha2":"PH","name":"Philippines","region":"South-eastern Asia","continent":"Asia","olympic_code":"PHI","fie_code":"PHI","aliases":["PHILIPPINES"],"latitude":12.8797,"longitude":121.774},
  {"alpha3":"POL","alpha2":"PL","name":"Poland","region":"Eastern Europe","continent":"Europe","olympic_code":"POL","fie_code":"POL","aliases":["POLAND"],"latitude":51.9194,"longitude":19.1451},
  {"alpha3":"PRT","alpha2":"PT","name":"Portugal","region":"Southern Europe","continent":"Europe","olympic_code":"POR","fie_code":"POR","aliases":["PORTUGAL"],"latitude":39.3999,"longitude":-8.2245},
  {"alpha3":"PRY","alpha2":"PY","name":"Paraguay","region":"South America","continent":"Americas","olympic_code":"PAR","fie_code":"PAR","aliases":["PARAGUAY"],"latitude":-23.4425,"longitude":-58.4438},
  {"alpha3":"PSE","alpha2":"PS","name":"Palestine","region":"Western Asia","continent":"Asia","olympic_code":"PLE","fie_code":"PLE","aliases":["PALESTINE"],"latitude":31.9522,"longitude":35.2332},
  {"alpha3":"PUR","alpha2":"PR","name":"Puerto Rico","region":"Caribbean","continent":"Americas","olympic_code":"PUR","fie_code":"PUR","aliases":["PUERTO RICO"],"latitude":18.2208,"longitude":-66.5901},
  {"alpha3":"QAT","alpha2":"QA","name":"Qatar","region":"Western Asia","continent":"Asia","olympic_code":"QAT","fie_code":"QAT","aliases":["QATAR"],"latitude":25.3548,"longitude":51.1839},
  {"alpha3":"ROC","alpha2":null,"name":"Russian Olympic Committee","region":"Historical","continent":"Europe","olympic_code":"ROC","fie_code":null,"aliases":["RUSSIAN OLYMPIC COMMITTEE"],"latitude":null,"longitude":null},
  {"alpha3":"ROU","alpha2":"RO","name":"Romania","region":"Eastern Europe","continent":"Europe","olympic_code":"ROU","fie_code":"ROU","aliases":["ROMANIA"],"latitude":45.9432,"longitude":24.9668},
  {"alpha3":"RUS","alpha2":"RU","name":"Russia","region":"Eastern Europe","continent":"Europe","olympic_code":"RUS","fie_code":"RUS","aliases":["RUSSIA","RUSSIAN FEDERATION"],"latitude":61.524,"longitude":105.3188},
  {"alpha3":"SCG","alpha2":null,"name":"Serbia and Montenegro","region":"Historical","continent":"Europe","olympic_code":"SCG","fie_code":null,"aliases":["SERBIA AND MONTENEGRO"],"latitude":44.0165,"longitude":21.0059},
  {"alpha3":"SCO","alpha2":null,"name":"Scotland","region":"Commonwealth","continent":"Europe","olympic_code":null,"fie_code":null,"aliases":["SCOT","SCOTLAND"],"latitude":56.4907,"longitude":-4.2026},
  {"alpha3":"SEN","alpha2":"SN","name":"Senegal","region":"Western Africa","continent":"Africa","olympic_code":"SEN","fie_code":"SEN","aliases":["SENEGAL"],"latitude":14.4974,"longitude":-14.4524},
  {"alpha3":"SGP","alpha2":"SG","name":"Singapore","region":"South-eastern Asia","continent":"Asia","olympic_code":"SGP","fie_code":"SGP","aliases":["SINGAPORE"],"latitude":1.3521,"longitude":103.8198},
  {"alpha3":"SLV","alpha2":"SV","name":"El Salvador","region":"Central America","continent":"Americas","olympic_code":"ESA","fie_code":"ESA","aliases":["EL SALVADOR"],"latitude":13.7942,"longitude":-88.8965},
  {"alpha3":"SRB","alpha2":"RS","name":"Serbia","region":"Southern Europe","continent":"Europe","olympic_code":"SRB","fie_code":"SRB","aliases":["SERBIA"],"latitude":44.0165,"longitude":21.0059},
  {"alpha3":"SUR","alpha2":"SR","name":"Suriname","region":"South America","continent":"Americas","olympic_code":"SUR","fie_code":"SUR","aliases":["SURINAME"],"latitude":3.9193,"longitude":-56.0278},
  {"alpha3":"SVK","alpha2":"SK","name":"Slovakia","region":"Eastern Europe","continent":"Europe","olympic_code":"SVK","fie_code":"SVK","aliases":["SLOVAKIA"],"latitude":48.669,"longitude":19.699},
  {"alpha3":"SVN","alpha2":"SI","name":"Slovenia","region":"Southern Europe","continent":"Europe","olympic_code":"SLO","fie_code":"SLO","aliases":["SLOVENIA"],"latitude":46.1512,"longitude":14.9955},
  {"alpha3":"SWE","alpha2":"SE","name":"Sweden","region":"Northern Europe","continent":"Europe","olympic_code":"SWE","fie_code":"SWE","aliases":["SWEDEN"],"latitude":60.1282,"longitude":18.6435},
  {"alpha3":"TCH","alpha2":null,"name":"Czechoslovakia","region":"Historical","continent":"Europe","olympic_code":"TCH","fie_code":null,"aliases":["CZECHOSLOVAKIA"],"latitude":49.8175,"longitude":15.473},
  {"alpha3":"THA","alpha2":"TH","name":"Thailand","region":"South-eastern Asia","continent":"Asia","olympic_code":"THA","fie_code":"THA","aliases":["THAILAND"],"latitude":15.87,"longitude":100.9925},
  {"alpha3":"TGO","alpha2":"TG","name":"Togo","region":"Western Africa","continent":"Africa","olympic_code":"TOG","fie_code":"TOG","aliases":["TOGO"],"latitude":8.6195,"longitude":0.8248},
  {"alpha3":"TUN","alpha2":"TN","name":"Tunisia","region":"Northern Africa","continent":"Africa","olympic_code":"TUN","fie_code":"TUN","aliases":["TUNISIA"],"latitude":33.8869,"longitude":9.5375},
  {"alpha3":"TUR","alpha2":"TR","name":"Turkey","region":"Western Asia","continent":"Asia","olympic_code":"TUR","fie_code":"TUR","aliases":["TURKIYE","TURKEY"],"latitude":38.9637,"longitude":35.2433},
  {"alpha3":"TWN","alpha2":"TW","name":"Chinese Taipei","region":"Eastern Asia","continent":"Asia","olympic_code":"TPE","fie_code":"TPE","aliases":["CHINESE TAIPEI","TAIWAN"],"latitude":23.6978,"longitude":120.9605},
  {"alpha3":"UKR","alpha2":"UA","name":"Ukraine","region":"Eastern Europe","continent":"Europe","olympic_code":"UKR","fie_code":"UKR","aliases":["UKRAINE"],"latitude":48.3794,"longitude":31.1656},
  {"alpha3":"URY","alpha2":"UY","name":"Uruguay","region":"South America","continent":"Americas","olympic_code":"URU","fie_code":"URU","aliases":["URUGUAY"],"latitude":-32.5228,"longitude":-55.7658},
  {"alpha3":"URS","alpha2":null,"name":"Soviet Union","region":"Historical","continent":"Europe/Asia","olympic_code":"URS","fie_code":null,"aliases":["SOVIET UNION","USSR"],"latitude":55.7558,"longitude":37.6173},
  {"alpha3":"USA","alpha2":"US","name":"United States","region":"Northern America","continent":"Americas","olympic_code":"USA","fie_code":"USA","aliases":["US","UNITED STATES","UNITED STATES OF AMERICA"],"latitude":39.7837,"longitude":-100.4459},
  {"alpha3":"UZB","alpha2":"UZ","name":"Uzbekistan","region":"Central Asia","continent":"Asia","olympic_code":"UZB","fie_code":"UZB","aliases":["UZBEKISTAN"],"latitude":41.3775,"longitude":64.5853},
  {"alpha3":"VCT","alpha2":"VC","name":"Saint Vincent and the Grenadines","region":"Caribbean","continent":"Americas","olympic_code":"VIN","fie_code":"VIN","aliases":["ST VINCENT","SAINT VINCENT","SAINT VINCENT AND THE GRENADINES"],"latitude":12.9843,"longitude":-61.2872},
  {"alpha3":"VEN","alpha2":"VE","name":"Venezuela","region":"South America","continent":"Americas","olympic_code":"VEN","fie_code":"VEN","aliases":["VENEZUELA"],"latitude":6.4238,"longitude":-66.5897},
  {"alpha3":"VNM","alpha2":"VN","name":"Vietnam","region":"South-eastern Asia","continent":"Asia","olympic_code":"VIE","fie_code":"VIE","aliases":["VIETNAM"],"latitude":14.0583,"longitude":108.2772},
  {"alpha3":"WAL","alpha2":null,"name":"Wales","region":"Commonwealth","continent":"Europe","olympic_code":null,"fie_code":null,"aliases":["WALES"],"latitude":52.1307,"longitude":-3.7837},
  {"alpha3":"YUG","alpha2":null,"name":"Yugoslavia","region":"Historical","continent":"Europe","olympic_code":"YUG","fie_code":null,"aliases":["YUGOSLAVIA"],"latitude":44.0165,"longitude":21.0059},
  {"alpha3":"ZAF","alpha2":"ZA","name":"South Africa","region":"Southern Africa","continent":"Africa","olympic_code":"RSA","fie_code":"RSA","aliases":["RSA","S.AFR","S AFR","SOUTH AFRICA"],"latitude":-30.5595,"longitude":22.9375}
]
$country_codes$::jsonb) AS x(
        alpha3 text,
        alpha2 text,
        name text,
        region text,
        continent text,
        flag_emoji text,
        olympic_code text,
        fie_code text,
        aliases text[],
        latitude numeric,
        longitude numeric
    )
)
INSERT INTO public.fs_country_codes (
    alpha3,
    alpha2,
    name,
    region,
    continent,
    flag_emoji,
    olympic_code,
    fie_code,
    aliases,
    latitude,
    longitude,
    updated_at
)
SELECT
    upper(seed.alpha3),
    nullif(upper(seed.alpha2), ''),
    seed.name,
    seed.region,
    seed.continent,
    COALESCE(
        seed.flag_emoji,
        CASE
            WHEN seed.alpha2 ~ '^[A-Za-z]{2}$' THEN
                chr(127397 + ascii(substr(upper(seed.alpha2), 1, 1))) ||
                chr(127397 + ascii(substr(upper(seed.alpha2), 2, 1)))
            ELSE NULL
        END
    ),
    nullif(upper(seed.olympic_code), ''),
    nullif(upper(seed.fie_code), ''),
    COALESCE(seed.aliases, '{}'::text[]),
    seed.latitude,
    seed.longitude,
    now()
FROM seed
ON CONFLICT (alpha3) DO UPDATE SET
    alpha2 = EXCLUDED.alpha2,
    name = EXCLUDED.name,
    region = EXCLUDED.region,
    continent = EXCLUDED.continent,
    flag_emoji = EXCLUDED.flag_emoji,
    olympic_code = EXCLUDED.olympic_code,
    fie_code = EXCLUDED.fie_code,
    aliases = EXCLUDED.aliases,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    updated_at = now();
