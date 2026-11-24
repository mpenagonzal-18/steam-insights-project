WITH ranked_games AS (
    SELECT EXTRACT(YEAR FROM date_release)::INTEGER AS release_year,
           app_id, title, positive_ratio, user_reviews,
           ROW_NUMBER() OVER (
               PARTITION BY EXTRACT(YEAR FROM date_release)
               ORDER BY positive_ratio DESC, user_reviews DESC NULLS LAST,
                        title ASC, app_id ASC
           ) AS position
    FROM steam.games
    WHERE date_release IS NOT NULL
      AND positive_ratio IS NOT NULL
      AND user_reviews >= 1000
)
SELECT release_year, position, app_id, title, positive_ratio, user_reviews
FROM ranked_games
WHERE position <= 3
ORDER BY release_year DESC, position ASC;