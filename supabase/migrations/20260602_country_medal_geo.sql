-- Country medal geography heatmap support.
-- Unrecognized country codes keep medal counts with null geo fields.

ALTER TABLE public.fs_results
    ADD COLUMN IF NOT EXISTS country text;

CREATE TABLE IF NOT EXISTS public.fs_country_geo_codes (
    country_code       text PRIMARY KEY,
    country_name       text NOT NULL,
    iso_alpha3         text,
    fie_code           text,
    olympic_code       text,
    latitude           double precision CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude          double precision CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    centroid_latitude  double precision CHECK (centroid_latitude IS NULL OR centroid_latitude BETWEEN -90 AND 90),
    centroid_longitude double precision CHECK (centroid_longitude IS NULL OR centroid_longitude BETWEEN -180 AND 180),
    updated_at         timestamptz NOT NULL DEFAULT timezone('utc'::text, now())
);

INSERT INTO public.fs_country_geo_codes (
    country_code,
    country_name,
    iso_alpha3,
    fie_code,
    olympic_code,
    latitude,
    longitude,
    centroid_latitude,
    centroid_longitude
) VALUES
    ('ALB', 'Albania', 'ALB', 'ALB', 'ALB', 41.1533, 20.1683, 41.1533, 20.1683),
    ('ALG', 'Algeria', 'DZA', 'ALG', 'ALG', 28.0339, 1.6596, 28.0339, 1.6596),
    ('AND', 'Andorra', 'AND', 'AND', 'AND', 42.5063, 1.5218, 42.5063, 1.5218),
    ('ANG', 'Angola', 'AGO', 'ANG', 'ANG', -11.2027, 17.8739, -11.2027, 17.8739),
    ('ANT', 'Antigua and Barbuda', 'ATG', 'ANT', 'ANT', 17.0608, -61.7964, 17.0608, -61.7964),
    ('ARG', 'Argentina', 'ARG', 'ARG', 'ARG', -38.4161, -63.6167, -38.4161, -63.6167),
    ('ARM', 'Armenia', 'ARM', 'ARM', 'ARM', 40.0691, 45.0382, 40.0691, 45.0382),
    ('ARU', 'Aruba', 'ABW', 'ARU', 'ARU', 12.5211, -69.9683, 12.5211, -69.9683),
    ('AUS', 'Australia', 'AUS', 'AUS', 'AUS', -25.2744, 133.7751, -25.2744, 133.7751),
    ('AUT', 'Austria', 'AUT', 'AUT', 'AUT', 47.5162, 14.5501, 47.5162, 14.5501),
    ('AZE', 'Azerbaijan', 'AZE', 'AZE', 'AZE', 40.1431, 47.5769, 40.1431, 47.5769),
    ('BAH', 'Bahamas', 'BHS', 'BAH', 'BAH', 25.0343, -77.3963, 25.0343, -77.3963),
    ('BRN', 'Bahrain', 'BHR', 'BRN', 'BRN', 26.0667, 50.5577, 26.0667, 50.5577),
    ('BAN', 'Bangladesh', 'BGD', 'BAN', 'BAN', 23.6850, 90.3563, 23.6850, 90.3563),
    ('BAR', 'Barbados', 'BRB', 'BAR', 'BAR', 13.1939, -59.5432, 13.1939, -59.5432),
    ('BLR', 'Belarus', 'BLR', 'BLR', 'BLR', 53.7098, 27.9534, 53.7098, 27.9534),
    ('BEL', 'Belgium', 'BEL', 'BEL', 'BEL', 50.5039, 4.4699, 50.5039, 4.4699),
    ('BIZ', 'Belize', 'BLZ', 'BIZ', 'BIZ', 17.1899, -88.4976, 17.1899, -88.4976),
    ('BEN', 'Benin', 'BEN', 'BEN', 'BEN', 9.3077, 2.3158, 9.3077, 2.3158),
    ('BER', 'Bermuda', 'BMU', 'BER', 'BER', 32.3078, -64.7505, 32.3078, -64.7505),
    ('BOL', 'Bolivia', 'BOL', 'BOL', 'BOL', -16.2902, -63.5887, -16.2902, -63.5887),
    ('BIH', 'Bosnia and Herzegovina', 'BIH', 'BIH', 'BIH', 43.9159, 17.6791, 43.9159, 17.6791),
    ('BOT', 'Botswana', 'BWA', 'BOT', 'BOT', -22.3285, 24.6849, -22.3285, 24.6849),
    ('BRA', 'Brazil', 'BRA', 'BRA', 'BRA', -14.2350, -51.9253, -14.2350, -51.9253),
    ('BUL', 'Bulgaria', 'BGR', 'BUL', 'BUL', 42.7339, 25.4858, 42.7339, 25.4858),
    ('BUR', 'Burkina Faso', 'BFA', 'BUR', 'BUR', 12.2383, -1.5616, 12.2383, -1.5616),
    ('CAM', 'Cambodia', 'KHM', 'CAM', 'CAM', 12.5657, 104.9910, 12.5657, 104.9910),
    ('CMR', 'Cameroon', 'CMR', 'CMR', 'CMR', 7.3697, 12.3547, 7.3697, 12.3547),
    ('CAN', 'Canada', 'CAN', 'CAN', 'CAN', 56.1304, -106.3468, 56.1304, -106.3468),
    ('CHI', 'Chile', 'CHL', 'CHI', 'CHI', -35.6751, -71.5430, -35.6751, -71.5430),
    ('CHN', 'China', 'CHN', 'CHN', 'CHN', 35.8617, 104.1954, 35.8617, 104.1954),
    ('COL', 'Colombia', 'COL', 'COL', 'COL', 4.5709, -74.2973, 4.5709, -74.2973),
    ('CRC', 'Costa Rica', 'CRI', 'CRC', 'CRC', 9.7489, -83.7534, 9.7489, -83.7534),
    ('CIV', 'Cote d''Ivoire', 'CIV', 'CIV', 'CIV', 7.5400, -5.5471, 7.5400, -5.5471),
    ('CRO', 'Croatia', 'HRV', 'CRO', 'CRO', 45.1000, 15.2000, 45.1000, 15.2000),
    ('CUB', 'Cuba', 'CUB', 'CUB', 'CUB', 21.5218, -77.7812, 21.5218, -77.7812),
    ('CYP', 'Cyprus', 'CYP', 'CYP', 'CYP', 35.1264, 33.4299, 35.1264, 33.4299),
    ('CZE', 'Czechia', 'CZE', 'CZE', 'CZE', 49.8175, 15.4730, 49.8175, 15.4730),
    ('DEN', 'Denmark', 'DNK', 'DEN', 'DEN', 56.2639, 9.5018, 56.2639, 9.5018),
    ('DOM', 'Dominican Republic', 'DOM', 'DOM', 'DOM', 18.7357, -70.1627, 18.7357, -70.1627),
    ('ECU', 'Ecuador', 'ECU', 'ECU', 'ECU', -1.8312, -78.1834, -1.8312, -78.1834),
    ('EGY', 'Egypt', 'EGY', 'EGY', 'EGY', 26.8206, 30.8025, 26.8206, 30.8025),
    ('ESA', 'El Salvador', 'SLV', 'ESA', 'ESA', 13.7942, -88.8965, 13.7942, -88.8965),
    ('EST', 'Estonia', 'EST', 'EST', 'EST', 58.5953, 25.0136, 58.5953, 25.0136),
    ('ETH', 'Ethiopia', 'ETH', 'ETH', 'ETH', 9.1450, 40.4897, 9.1450, 40.4897),
    ('FIJ', 'Fiji', 'FJI', 'FIJ', 'FIJ', -17.7134, 178.0650, -17.7134, 178.0650),
    ('FIN', 'Finland', 'FIN', 'FIN', 'FIN', 61.9241, 25.7482, 61.9241, 25.7482),
    ('FRA', 'France', 'FRA', 'FRA', 'FRA', 46.2276, 2.2137, 46.2276, 2.2137),
    ('GEO', 'Georgia', 'GEO', 'GEO', 'GEO', 42.3154, 43.3569, 42.3154, 43.3569),
    ('GER', 'Germany', 'DEU', 'GER', 'GER', 51.1657, 10.4515, 51.1657, 10.4515),
    ('GHA', 'Ghana', 'GHA', 'GHA', 'GHA', 7.9465, -1.0232, 7.9465, -1.0232),
    ('GBR', 'Great Britain', 'GBR', 'GBR', 'GBR', 55.3781, -3.4360, 55.3781, -3.4360),
    ('GRE', 'Greece', 'GRC', 'GRE', 'GRE', 39.0742, 21.8243, 39.0742, 21.8243),
    ('GUA', 'Guatemala', 'GTM', 'GUA', 'GUA', 15.7835, -90.2308, 15.7835, -90.2308),
    ('HON', 'Honduras', 'HND', 'HON', 'HON', 15.2000, -86.2419, 15.2000, -86.2419),
    ('HKG', 'Hong Kong', 'HKG', 'HKG', 'HKG', 22.3193, 114.1694, 22.3193, 114.1694),
    ('HUN', 'Hungary', 'HUN', 'HUN', 'HUN', 47.1625, 19.5033, 47.1625, 19.5033),
    ('ISL', 'Iceland', 'ISL', 'ISL', 'ISL', 64.9631, -19.0208, 64.9631, -19.0208),
    ('IND', 'India', 'IND', 'IND', 'IND', 20.5937, 78.9629, 20.5937, 78.9629),
    ('INA', 'Indonesia', 'IDN', 'INA', 'INA', -0.7893, 113.9213, -0.7893, 113.9213),
    ('IRI', 'Iran', 'IRN', 'IRI', 'IRI', 32.4279, 53.6880, 32.4279, 53.6880),
    ('IRQ', 'Iraq', 'IRQ', 'IRQ', 'IRQ', 33.2232, 43.6793, 33.2232, 43.6793),
    ('IRL', 'Ireland', 'IRL', 'IRL', 'IRL', 53.1424, -7.6921, 53.1424, -7.6921),
    ('ISR', 'Israel', 'ISR', 'ISR', 'ISR', 31.0461, 34.8516, 31.0461, 34.8516),
    ('ITA', 'Italy', 'ITA', 'ITA', 'ITA', 41.8719, 12.5674, 41.8719, 12.5674),
    ('JAM', 'Jamaica', 'JAM', 'JAM', 'JAM', 18.1096, -77.2975, 18.1096, -77.2975),
    ('JPN', 'Japan', 'JPN', 'JPN', 'JPN', 36.2048, 138.2529, 36.2048, 138.2529),
    ('JOR', 'Jordan', 'JOR', 'JOR', 'JOR', 30.5852, 36.2384, 30.5852, 36.2384),
    ('KAZ', 'Kazakhstan', 'KAZ', 'KAZ', 'KAZ', 48.0196, 66.9237, 48.0196, 66.9237),
    ('KEN', 'Kenya', 'KEN', 'KEN', 'KEN', -0.0236, 37.9062, -0.0236, 37.9062),
    ('KOS', 'Kosovo', 'XKX', 'KOS', 'KOS', 42.6026, 20.9030, 42.6026, 20.9030),
    ('KUW', 'Kuwait', 'KWT', 'KUW', 'KUW', 29.3117, 47.4818, 29.3117, 47.4818),
    ('KGZ', 'Kyrgyzstan', 'KGZ', 'KGZ', 'KGZ', 41.2044, 74.7661, 41.2044, 74.7661),
    ('LAT', 'Latvia', 'LVA', 'LAT', 'LAT', 56.8796, 24.6032, 56.8796, 24.6032),
    ('LIB', 'Lebanon', 'LBN', 'LIB', 'LIB', 33.8547, 35.8623, 33.8547, 35.8623),
    ('LBA', 'Libya', 'LBY', 'LBA', 'LBA', 26.3351, 17.2283, 26.3351, 17.2283),
    ('LIE', 'Liechtenstein', 'LIE', 'LIE', 'LIE', 47.1660, 9.5554, 47.1660, 9.5554),
    ('LTU', 'Lithuania', 'LTU', 'LTU', 'LTU', 55.1694, 23.8813, 55.1694, 23.8813),
    ('LUX', 'Luxembourg', 'LUX', 'LUX', 'LUX', 49.8153, 6.1296, 49.8153, 6.1296),
    ('MAC', 'Macau', 'MAC', 'MAC', 'MAC', 22.1987, 113.5439, 22.1987, 113.5439),
    ('MAS', 'Malaysia', 'MYS', 'MAS', 'MAS', 4.2105, 101.9758, 4.2105, 101.9758),
    ('MLT', 'Malta', 'MLT', 'MLT', 'MLT', 35.9375, 14.3754, 35.9375, 14.3754),
    ('MAR', 'Morocco', 'MAR', 'MAR', 'MAR', 31.7917, -7.0926, 31.7917, -7.0926),
    ('MEX', 'Mexico', 'MEX', 'MEX', 'MEX', 23.6345, -102.5528, 23.6345, -102.5528),
    ('MDA', 'Moldova', 'MDA', 'MDA', 'MDA', 47.4116, 28.3699, 47.4116, 28.3699),
    ('MON', 'Monaco', 'MCO', 'MON', 'MON', 43.7384, 7.4246, 43.7384, 7.4246),
    ('MGL', 'Mongolia', 'MNG', 'MGL', 'MGL', 46.8625, 103.8467, 46.8625, 103.8467),
    ('MNE', 'Montenegro', 'MNE', 'MNE', 'MNE', 42.7087, 19.3744, 42.7087, 19.3744),
    ('MOZ', 'Mozambique', 'MOZ', 'MOZ', 'MOZ', -18.6657, 35.5296, -18.6657, 35.5296),
    ('MYA', 'Myanmar', 'MMR', 'MYA', 'MYA', 21.9162, 95.9560, 21.9162, 95.9560),
    ('NAM', 'Namibia', 'NAM', 'NAM', 'NAM', -22.9576, 18.4904, -22.9576, 18.4904),
    ('NEP', 'Nepal', 'NPL', 'NEP', 'NEP', 28.3949, 84.1240, 28.3949, 84.1240),
    ('NED', 'Netherlands', 'NLD', 'NED', 'NED', 52.1326, 5.2913, 52.1326, 5.2913),
    ('NZL', 'New Zealand', 'NZL', 'NZL', 'NZL', -40.9006, 174.8860, -40.9006, 174.8860),
    ('NCA', 'Nicaragua', 'NIC', 'NCA', 'NCA', 12.8654, -85.2072, 12.8654, -85.2072),
    ('NGR', 'Nigeria', 'NGA', 'NGR', 'NGR', 9.0820, 8.6753, 9.0820, 8.6753),
    ('MKD', 'North Macedonia', 'MKD', 'MKD', 'MKD', 41.6086, 21.7453, 41.6086, 21.7453),
    ('NOR', 'Norway', 'NOR', 'NOR', 'NOR', 60.4720, 8.4689, 60.4720, 8.4689),
    ('OMA', 'Oman', 'OMN', 'OMA', 'OMA', 21.4735, 55.9754, 21.4735, 55.9754),
    ('PAK', 'Pakistan', 'PAK', 'PAK', 'PAK', 30.3753, 69.3451, 30.3753, 69.3451),
    ('PLE', 'Palestine', 'PSE', 'PLE', 'PLE', 31.9522, 35.2332, 31.9522, 35.2332),
    ('PAN', 'Panama', 'PAN', 'PAN', 'PAN', 8.5380, -80.7821, 8.5380, -80.7821),
    ('PAR', 'Paraguay', 'PRY', 'PAR', 'PAR', -23.4425, -58.4438, -23.4425, -58.4438),
    ('PER', 'Peru', 'PER', 'PER', 'PER', -9.1900, -75.0152, -9.1900, -75.0152),
    ('PHI', 'Philippines', 'PHL', 'PHI', 'PHI', 12.8797, 121.7740, 12.8797, 121.7740),
    ('POL', 'Poland', 'POL', 'POL', 'POL', 51.9194, 19.1451, 51.9194, 19.1451),
    ('POR', 'Portugal', 'PRT', 'POR', 'POR', 39.3999, -8.2245, 39.3999, -8.2245),
    ('PUR', 'Puerto Rico', 'PRI', 'PUR', 'PUR', 18.2208, -66.5901, 18.2208, -66.5901),
    ('QAT', 'Qatar', 'QAT', 'QAT', 'QAT', 25.3548, 51.1839, 25.3548, 51.1839),
    ('ROU', 'Romania', 'ROU', 'ROU', 'ROU', 45.9432, 24.9668, 45.9432, 24.9668),
    ('RUS', 'Russia', 'RUS', 'RUS', 'RUS', 61.5240, 105.3188, 61.5240, 105.3188),
    ('SMR', 'San Marino', 'SMR', 'SMR', 'SMR', 43.9424, 12.4578, 43.9424, 12.4578),
    ('KSA', 'Saudi Arabia', 'SAU', 'KSA', 'KSA', 23.8859, 45.0792, 23.8859, 45.0792),
    ('SEN', 'Senegal', 'SEN', 'SEN', 'SEN', 14.4974, -14.4524, 14.4974, -14.4524),
    ('SRB', 'Serbia', 'SRB', 'SRB', 'SRB', 44.0165, 21.0059, 44.0165, 21.0059),
    ('SGP', 'Singapore', 'SGP', 'SGP', 'SGP', 1.3521, 103.8198, 1.3521, 103.8198),
    ('SVK', 'Slovakia', 'SVK', 'SVK', 'SVK', 48.6690, 19.6990, 48.6690, 19.6990),
    ('SLO', 'Slovenia', 'SVN', 'SLO', 'SLO', 46.1512, 14.9955, 46.1512, 14.9955),
    ('RSA', 'South Africa', 'ZAF', 'RSA', 'RSA', -30.5595, 22.9375, -30.5595, 22.9375),
    ('KOR', 'South Korea', 'KOR', 'KOR', 'KOR', 35.9078, 127.7669, 35.9078, 127.7669),
    ('PRK', 'North Korea', 'PRK', 'PRK', 'PRK', 40.3399, 127.5101, 40.3399, 127.5101),
    ('ESP', 'Spain', 'ESP', 'ESP', 'ESP', 40.4637, -3.7492, 40.4637, -3.7492),
    ('SRI', 'Sri Lanka', 'LKA', 'SRI', 'SRI', 7.8731, 80.7718, 7.8731, 80.7718),
    ('SWE', 'Sweden', 'SWE', 'SWE', 'SWE', 60.1282, 18.6435, 60.1282, 18.6435),
    ('SUI', 'Switzerland', 'CHE', 'SUI', 'SUI', 46.8182, 8.2275, 46.8182, 8.2275),
    ('SYR', 'Syria', 'SYR', 'SYR', 'SYR', 34.8021, 38.9968, 34.8021, 38.9968),
    ('TPE', 'Chinese Taipei', 'TWN', 'TPE', 'TPE', 23.6978, 120.9605, 23.6978, 120.9605),
    ('TJK', 'Tajikistan', 'TJK', 'TJK', 'TJK', 38.8610, 71.2761, 38.8610, 71.2761),
    ('THA', 'Thailand', 'THA', 'THA', 'THA', 15.8700, 100.9925, 15.8700, 100.9925),
    ('TTO', 'Trinidad and Tobago', 'TTO', 'TTO', 'TTO', 10.6918, -61.2225, 10.6918, -61.2225),
    ('TUN', 'Tunisia', 'TUN', 'TUN', 'TUN', 33.8869, 9.5375, 33.8869, 9.5375),
    ('TUR', 'Turkey', 'TUR', 'TUR', 'TUR', 38.9637, 35.2433, 38.9637, 35.2433),
    ('TKM', 'Turkmenistan', 'TKM', 'TKM', 'TKM', 38.9697, 59.5563, 38.9697, 59.5563),
    ('UGA', 'Uganda', 'UGA', 'UGA', 'UGA', 1.3733, 32.2903, 1.3733, 32.2903),
    ('UKR', 'Ukraine', 'UKR', 'UKR', 'UKR', 48.3794, 31.1656, 48.3794, 31.1656),
    ('UAE', 'United Arab Emirates', 'ARE', 'UAE', 'UAE', 23.4241, 53.8478, 23.4241, 53.8478),
    ('URU', 'Uruguay', 'URY', 'URU', 'URU', -32.5228, -55.7658, -32.5228, -55.7658),
    ('USA', 'United States', 'USA', 'USA', 'USA', 37.0902, -95.7129, 37.0902, -95.7129),
    ('UZB', 'Uzbekistan', 'UZB', 'UZB', 'UZB', 41.3775, 64.5853, 41.3775, 64.5853),
    ('VEN', 'Venezuela', 'VEN', 'VEN', 'VEN', 6.4238, -66.5897, 6.4238, -66.5897),
    ('VIE', 'Vietnam', 'VNM', 'VIE', 'VIE', 14.0583, 108.2772, 14.0583, 108.2772),
    ('ZAM', 'Zambia', 'ZMB', 'ZAM', 'ZAM', -13.1339, 27.8493, -13.1339, 27.8493),
    ('ZIM', 'Zimbabwe', 'ZWE', 'ZIM', 'ZIM', -19.0154, 29.1549, -19.0154, 29.1549),
    ('AIN', 'Individual Neutral Athletes', NULL, 'AIN', 'AIN', NULL, NULL, NULL, NULL),
    ('EOR', 'Refugee Olympic Team', NULL, NULL, 'EOR', NULL, NULL, NULL, NULL),
    ('FIE', 'International Fencing Federation', NULL, 'FIE', NULL, NULL, NULL, NULL, NULL),
    ('IOA', 'Independent Olympic Athletes', NULL, NULL, 'IOA', NULL, NULL, NULL, NULL),
    ('MIX', 'Mixed Team', NULL, NULL, 'MIX', NULL, NULL, NULL, NULL),
    ('ROC', 'Russian Olympic Committee', NULL, NULL, 'ROC', NULL, NULL, NULL, NULL),
    ('UNK', 'Unknown', NULL, NULL, NULL, NULL, NULL, NULL, NULL)
ON CONFLICT (country_code) DO UPDATE SET
    country_name = EXCLUDED.country_name,
    iso_alpha3 = EXCLUDED.iso_alpha3,
    fie_code = EXCLUDED.fie_code,
    olympic_code = EXCLUDED.olympic_code,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    centroid_latitude = EXCLUDED.centroid_latitude,
    centroid_longitude = EXCLUDED.centroid_longitude,
    updated_at = timezone('utc'::text, now());

CREATE INDEX IF NOT EXISTS fs_country_geo_codes_iso_alpha3_idx
    ON public.fs_country_geo_codes (iso_alpha3)
    WHERE iso_alpha3 IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_country_geo_codes_fie_code_idx
    ON public.fs_country_geo_codes (fie_code)
    WHERE fie_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS fs_country_geo_codes_olympic_code_idx
    ON public.fs_country_geo_codes (olympic_code)
    WHERE olympic_code IS NOT NULL;

CREATE MATERIALIZED VIEW IF NOT EXISTS public.fs_country_medal_geo AS
WITH country_aliases AS (
    SELECT country_code, upper(country_code) AS country_token, 1 AS priority
    FROM public.fs_country_geo_codes
    UNION ALL
    SELECT country_code, upper(iso_alpha3) AS country_token, 2 AS priority
    FROM public.fs_country_geo_codes
    WHERE iso_alpha3 IS NOT NULL
    UNION ALL
    SELECT country_code, upper(fie_code) AS country_token, 3 AS priority
    FROM public.fs_country_geo_codes
    WHERE fie_code IS NOT NULL
    UNION ALL
    SELECT country_code, upper(olympic_code) AS country_token, 4 AS priority
    FROM public.fs_country_geo_codes
    WHERE olympic_code IS NOT NULL
    UNION ALL
    SELECT country_code, upper(country_name) AS country_token, 5 AS priority
    FROM public.fs_country_geo_codes
    UNION ALL
    SELECT *
    FROM (
        VALUES
            ('USA'::text, 'UNITED STATES OF AMERICA'::text, 6),
            ('GBR'::text, 'UNITED KINGDOM'::text, 6),
            ('KOR'::text, 'REPUBLIC OF KOREA'::text, 6),
            ('KOR'::text, 'SOUTH KOREA'::text, 6),
            ('PRK'::text, 'NORTH KOREA'::text, 6),
            ('IRI'::text, 'IRAN'::text, 6),
            ('UAE'::text, 'UNITED ARAB EMIRATES'::text, 6),
            ('CIV'::text, 'IVORY COAST'::text, 6),
            ('CZE'::text, 'CZECH REPUBLIC'::text, 6),
            ('TPE'::text, 'TAIWAN'::text, 6),
            ('HKG'::text, 'HONG KONG CHINA'::text, 6),
            ('MAC'::text, 'MACAU CHINA'::text, 6),
            ('MDA'::text, 'MOLDOVA REPUBLIC OF'::text, 6),
            ('PLE'::text, 'PALESTINIAN TERRITORIES'::text, 6)
    ) AS aliases(country_code, country_token, priority)
),
source_results AS (
    SELECT
        COALESCE(NULLIF(upper(trim(r.country)), ''), NULLIF(upper(trim(r.nationality)), '')) AS country_token,
        COALESCE(NULLIF(t.weapon, ''), 'unknown') AS weapon,
        COALESCE(NULLIF(t.category, ''), 'unknown') AS category,
        CASE
            WHEN regexp_replace(upper(COALESCE(t.type::text, '')), '[^A-Z0-9]+', '', 'g')
                IN ('OG', 'OLYMPICS', 'OLYMPICGAMES')
                OR lower(COALESCE(t.name, '')) LIKE '%olympic%'
                THEN 'Olympics'
            WHEN regexp_replace(upper(COALESCE(t.type::text, '')), '[^A-Z0-9]+', '', 'g')
                IN ('WCH', 'CHM', 'WORLDCHAMPIONSHIP', 'WORLDCHAMPIONSHIPS', 'WORLDS')
                OR lower(COALESCE(t.name, '')) LIKE '%world championship%'
                OR lower(COALESCE(t.name, '')) LIKE '%worlds%'
                THEN 'Worlds'
            WHEN regexp_replace(upper(COALESCE(t.type::text, '')), '[^A-Z0-9]+', '', 'g')
                IN ('GP', 'GRANDPRIX')
                OR lower(COALESCE(t.name, '')) LIKE '%grand prix%'
                THEN 'Grand Prix'
            WHEN regexp_replace(upper(COALESCE(t.type::text, '')), '[^A-Z0-9]+', '', 'g')
                IN ('WC', 'WORLDCUP')
                OR lower(COALESCE(t.name, '')) LIKE '%world cup%'
                THEN 'World Cup'
            WHEN regexp_replace(upper(COALESCE(t.type::text, '')), '[^A-Z0-9]+', '', 'g')
                IN ('CC', 'ZCH', 'CONTINENTALCHAMPIONSHIP', 'CONTINENTALCHAMPIONSHIPS', 'ZONALCHAMPIONSHIP', 'ZONALCHAMPIONSHIPS')
                OR lower(COALESCE(t.name, '')) LIKE '%continental%'
                OR lower(COALESCE(t.name, '')) LIKE '%zonal%'
                OR lower(COALESCE(t.name, '')) LIKE '%european championship%'
                OR lower(COALESCE(t.name, '')) LIKE '%asian championship%'
                OR lower(COALESCE(t.name, '')) LIKE '%pan american championship%'
                OR lower(COALESCE(t.name, '')) LIKE '%african championship%'
                THEN 'Continental'
            ELSE COALESCE(NULLIF(t.type::text, ''), 'unknown')
        END AS competition_tier,
        NULLIF(t.season::text, '') AS season,
        CASE
            WHEN t.start_date IS NOT NULL THEN extract(year from t.start_date)::integer
            WHEN t.end_date IS NOT NULL THEN extract(year from t.end_date)::integer
            WHEN t.season::text ~ '^[0-9]{4}$' THEN t.season::integer
            WHEN t.season::text ~ '^[0-9]{4}-[0-9]{4}$' THEN substring(t.season::text from 6 for 4)::integer
            ELSE NULL
        END AS year,
        CASE regexp_replace(lower(COALESCE(r.medal::text, '')), '[^a-z0-9]+', '', 'g')
            WHEN 'gold' THEN 'gold'
            WHEN 'g' THEN 'gold'
            WHEN '1' THEN 'gold'
            WHEN '1st' THEN 'gold'
            WHEN 'silver' THEN 'silver'
            WHEN 's' THEN 'silver'
            WHEN '2' THEN 'silver'
            WHEN '2nd' THEN 'silver'
            WHEN 'bronze' THEN 'bronze'
            WHEN 'b' THEN 'bronze'
            WHEN '3' THEN 'bronze'
            WHEN '3rd' THEN 'bronze'
            ELSE NULL
        END AS medal_bucket,
        CASE
            WHEN r.rank::text ~ '^[0-9]+$' THEN r.rank::integer
            ELSE NULL
        END AS rank_int
    FROM public.fs_results r
    LEFT JOIN public.fs_tournaments t
        ON t.id = r.tournament_id
),
coded_results AS (
    SELECT
        COALESCE(
            country_match.country_code,
            NULLIF(regexp_replace(source_results.country_token, '[^A-Z0-9]+', '', 'g'), '')
        ) AS country_code,
        source_results.weapon,
        source_results.category,
        source_results.competition_tier,
        source_results.season,
        source_results.year,
        source_results.medal_bucket,
        source_results.rank_int
    FROM source_results
    LEFT JOIN LATERAL (
        SELECT country_aliases.country_code
        FROM country_aliases
        WHERE country_aliases.country_token = source_results.country_token
        ORDER BY country_aliases.priority ASC
        LIMIT 1
    ) AS country_match ON true
    WHERE source_results.country_token IS NOT NULL
),
medals AS (
    SELECT
        country_code,
        weapon,
        category,
        competition_tier,
        season,
        year,
        COUNT(*) FILTER (WHERE medal_bucket = 'gold')::integer AS gold_count,
        COUNT(*) FILTER (WHERE medal_bucket = 'silver')::integer AS silver_count,
        COUNT(*) FILTER (WHERE medal_bucket = 'bronze')::integer AS bronze_count,
        COUNT(*) FILTER (WHERE medal_bucket IN ('gold', 'silver', 'bronze'))::integer AS total_medals,
        COUNT(*) FILTER (WHERE rank_int BETWEEN 1 AND 8)::integer AS top8_count,
        COUNT(*) FILTER (WHERE rank_int BETWEEN 1 AND 16)::integer AS top16_count
    FROM coded_results
    WHERE country_code IS NOT NULL
      AND (
          medal_bucket IN ('gold', 'silver', 'bronze')
          OR rank_int BETWEEN 1 AND 16
      )
    GROUP BY
        country_code,
        weapon,
        category,
        competition_tier,
        season,
        year
)
SELECT
    medals.country_code,
    geo.country_name,
    geo.fie_code,
    geo.olympic_code,
    medals.weapon,
    medals.category,
    medals.competition_tier,
    medals.season,
    medals.year,
    medals.gold_count,
    medals.silver_count,
    medals.bronze_count,
    medals.total_medals,
    medals.top8_count,
    medals.top16_count,
    geo.latitude,
    geo.longitude,
    geo.centroid_latitude,
    geo.centroid_longitude,
    timezone('utc'::text, now()) AS refreshed_at
FROM medals
LEFT JOIN public.fs_country_geo_codes geo
    ON geo.country_code = medals.country_code
ORDER BY
    medals.total_medals DESC,
    medals.top8_count DESC,
    medals.country_code,
    medals.weapon,
    medals.category,
    medals.competition_tier,
    medals.season,
    medals.year;

CREATE UNIQUE INDEX IF NOT EXISTS fs_country_medal_geo_unique_idx
    ON public.fs_country_medal_geo (
        country_code,
        weapon,
        category,
        competition_tier,
        season,
        year
    );

CREATE INDEX IF NOT EXISTS fs_country_medal_geo_heatmap_idx
    ON public.fs_country_medal_geo (
        weapon,
        category,
        competition_tier,
        season,
        year,
        total_medals DESC
    );

CREATE INDEX IF NOT EXISTS fs_country_medal_geo_country_idx
    ON public.fs_country_medal_geo (country_code, total_medals DESC);

ALTER MATERIALIZED VIEW public.fs_country_medal_geo OWNER TO service_role;

CREATE OR REPLACE FUNCTION public.refresh_country_medal_geo()
RETURNS void
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW public.fs_country_medal_geo;
END;
$$;

REVOKE ALL ON public.fs_country_geo_codes FROM PUBLIC;
REVOKE ALL ON public.fs_country_medal_geo FROM PUBLIC;
REVOKE ALL ON FUNCTION public.refresh_country_medal_geo() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.refresh_country_medal_geo() FROM anon, authenticated;

GRANT SELECT ON public.fs_country_geo_codes TO service_role;
GRANT SELECT ON public.fs_country_medal_geo TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.refresh_country_medal_geo() TO service_role;
