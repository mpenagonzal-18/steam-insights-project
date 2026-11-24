SELECT g.app_id, g.title, g.rating,
       g.positive_ratio, g.user_reviews,
       (SELECT ROUND(AVG(g2.positive_ratio), 2)
        FROM steam.games AS g2
        WHERE g2.rating = g.rating
          AND g2.positive_ratio IS NOT NULL
          AND g2.user_reviews >= 1000) AS category_avg_ratio
FROM steam.games AS g
WHERE g.rating IS NOT NULL
  AND g.positive_ratio IS NOT NULL
  AND g.user_reviews >= 1000
  AND g.positive_ratio > (
      SELECT AVG(g3.positive_ratio)
      FROM steam.games AS g3
      WHERE g3.rating = g.rating
        AND g3.positive_ratio IS NOT NULL
        AND g3.user_reviews >= 1000
  )
ORDER BY g.positive_ratio DESC, g.user_reviews DESC, g.app_id ASC
LIMIT 30;