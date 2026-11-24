SELECT tag_name, COUNT(steam.game_tags.app_id) AS total_games
FROM steam.tags
JOIN steam.game_tags ON steam.game_tags.tag_id = steam.tags.tag_id
GROUP BY steam.tags.tag_id, steam.tags.tag_name
ORDER BY total_games DESC, steam.tags.tag_name
LIMIT 15;