/* semantic search & fuzzy search
we opted for the use of using trigram similarity (optimised with GIN indexing) over Levenshtein distance
to allow for fast fuzzy-search querying over the database. */

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX name_trgm_idx ON acousticbrainz_data USING gin (name gin_trgm_ops);
CREATE INDEX artist_trgm_idx ON acousticbrainz_data USING gin (artist gin_trgm_ops);

SELECT *
FROM acousticbrainz_data
WHERE 
    similarity(name, %(q)s) > 0.25 OR
    similarity(artist, %(q)s) > 0.25
ORDER BY 
    GREATEST(similarity(name, %(q)s), similarity(artist, %(q)s))
LIMIT 5; 

/* need to find out if statements, if there's nothing relevant then maybe give an error message? based on some Levenshtein Distance? */