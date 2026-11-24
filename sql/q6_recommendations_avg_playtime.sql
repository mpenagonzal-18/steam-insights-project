SELECT CASE WHEN is_recommended THEN 'Recommended'
            ELSE 'Not recommended' END AS review_group,
       COUNT(*) AS reviews_with_hours,
       ROUND(AVG(hours), 2) AS avg_hours,
       ROUND(AVG(helpful), 2) AS avg_helpful_votes
FROM steam.recommendations
WHERE is_recommended IS NOT NULL
  AND hours IS NOT NULL
GROUP BY is_recommended
ORDER BY is_recommended DESC;