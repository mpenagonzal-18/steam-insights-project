SELECT steam.games.app_id, steam.games.title,
       COUNT(*) AS positive_recommendations
FROM steam.recommendations
JOIN steam.games ON steam.games.app_id = steam.recommendations.app_id
WHERE steam.recommendations.is_recommended IS TRUE
GROUP BY steam.games.app_id, steam.games.title
ORDER BY positive_recommendations DESC, steam.games.title
LIMIT 10;