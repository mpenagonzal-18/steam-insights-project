SELECT platform_name, COUNT(steam.game_platforms.app_id) AS total_games
FROM steam.platforms
LEFT JOIN steam.game_platforms ON steam.game_platforms.platform_id = steam.platforms.platform_id
GROUP BY steam.platforms.platform_id, steam.platforms.platform_name
ORDER BY total_games DESC, steam.platforms.platform_name;