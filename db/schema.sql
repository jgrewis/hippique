PRAGMA foreign_keys = ON;

-- One row per race. id_course is a natural key: YYYY-MM-DD-R{n}C{m}.
CREATE TABLE IF NOT EXISTS courses (
    id_course      TEXT PRIMARY KEY,
    date_course    TEXT NOT NULL,           -- YYYY-MM-DD
    num_reunion    INTEGER NOT NULL,
    num_course     INTEGER NOT NULL,
    hippodrome     TEXT NOT NULL,
    discipline     TEXT,                    -- Attelé, Monté, Plat, Obstacle
    specialite     TEXT,
    distance_m     INTEGER,
    nb_partants    INTEGER,
    heure_depart   TEXT,                    -- HH:MM, Paris local time
    depart_ts      INTEGER,                 -- epoch milliseconds (UTC)
    nom_course     TEXT,
    montant_prix   INTEGER,                 -- euros
    categorie      TEXT,
    terrain        TEXT,
    paris          TEXT,                    -- comma list: TIERCE,QUARTE_PLUS,QUINTE_PLUS
    is_quinte      INTEGER NOT NULL DEFAULT 0,
    statut         TEXT,
    arrivee        TEXT,                    -- "7-8-6-4-12", NULL until official
    externes_ok    INTEGER NOT NULL DEFAULT 0,  -- third-party forecasts collected for good
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS partants (
    id_course       TEXT NOT NULL REFERENCES courses(id_course) ON DELETE CASCADE,
    numero          INTEGER NOT NULL,
    nom_cheval      TEXT NOT NULL,
    id_cheval       TEXT,
    age             INTEGER,
    sexe            TEXT,
    driver_jockey   TEXT,
    entraineur      TEXT,
    musique         TEXT,
    nb_courses      INTEGER,
    nb_victoires    INTEGER,
    nb_places       INTEGER,
    gains_carriere  INTEGER,                -- euros
    poids_kg        REAL,
    corde           INTEGER,
    deferre         TEXT,
    cote_matin      REAL,
    cote_actuelle   REAL,
    non_partant     INTEGER NOT NULL DEFAULT 0,
    incident        TEXT,
    arrivee         INTEGER,                -- final position, NULL if not classified
    PRIMARY KEY (id_course, numero)
);

CREATE TABLE IF NOT EXISTS rapports (
    id_course    TEXT NOT NULL REFERENCES courses(id_course) ON DELETE CASCADE,
    type_pari    TEXT NOT NULL,             -- TIERCE, QUARTE_PLUS, QUINTE_PLUS, ...
    libelle      TEXT NOT NULL,             -- "Tiercé Ordre", "Bonus 4sur5", ...
    combinaison  TEXT NOT NULL,
    rapport      REAL,                      -- euros paid for a 1 € stake
    PRIMARY KEY (id_course, type_pari, libelle, combinaison)
);

-- Predictions are frozen once the race has started, so the reliability
-- page only ever scores forecasts that were really made before the race.
CREATE TABLE IF NOT EXISTS pronostics (
    id_course   TEXT NOT NULL REFERENCES courses(id_course) ON DELETE CASCADE,
    numero      INTEGER NOT NULL,
    methode     TEXT NOT NULL,              -- forme | logit | boosting | elo | consensus
    score       REAL,
    proba       REAL,
    rang        INTEGER,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (id_course, numero, methode)
);

-- Third-party rankings: PMU forecast, press, most-played bets. Only numbers
-- and the source name are stored, never the authors' texts (copyright).
CREATE TABLE IF NOT EXISTS selections (
    id_course     TEXT NOT NULL REFERENCES courses(id_course) ON DELETE CASCADE,
    source        TEXT NOT NULL,            -- stable key: pmu, presse:le-parisien, joues:TIERCE:1, ...
    famille       TEXT NOT NULL,            -- pmu | presse | synthese | parieurs
    libelle       TEXT NOT NULL,            -- display name
    numeros       TEXT NOT NULL,            -- ranked runners: "6-1-4-14"
    avant_depart  INTEGER NOT NULL,         -- 1 if collected before the start of the race
    collected_at  TEXT NOT NULL,
    PRIMARY KEY (id_course, source)
);

CREATE TABLE IF NOT EXISTS collect_days (
    date_course  TEXT PRIMARY KEY,
    complete     INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collect_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at      TEXT NOT NULL,
    date_course TEXT,
    level       TEXT NOT NULL,              -- INFO | WARNING | ERROR
    message     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_courses_date ON courses(date_course);
CREATE INDEX IF NOT EXISTS idx_partants_cheval ON partants(id_cheval);
CREATE INDEX IF NOT EXISTS idx_rapports_course ON rapports(id_course);
CREATE INDEX IF NOT EXISTS idx_log_run ON collect_log(run_at);
