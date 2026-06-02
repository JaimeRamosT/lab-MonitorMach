-- Create pokemon_stats table with only required columns
CREATE TABLE IF NOT EXISTS pokemon_stats (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    hp INT NOT NULL,
    attack INT NOT NULL,
    defense INT NOT NULL,
    sp_atk INT NOT NULL,
    sp_def INT NOT NULL,
    speed INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on name for faster searches
CREATE INDEX IF NOT EXISTS idx_pokemon_stats_name ON pokemon_stats(name);
