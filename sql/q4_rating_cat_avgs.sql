SELECT rating,
       COUNT(*) AS total_games,
       ROUND(AVG(price_final), 2) AS avg_price,
       ROUND(AVG(positive_ratio), 2) AS avg_positive_ratio
FROM steam.games
WHERE rating IS NOT NULL
GROUP BY rating
HAVING COUNT(*) >= 30
ORDER BY avg_positive_ratio DESC NULLS LAST, total_games DESC, rating;