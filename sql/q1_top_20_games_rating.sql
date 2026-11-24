SELECT title,
	   date_release,
	   rating,
	   positive_ratio,
	   user_reviews
FROM steam.games
WHERE user_reviews > 1000
ORDER BY user_reviews DESC
LIMIT 20;