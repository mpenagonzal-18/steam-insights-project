BEGIN;
WITH targets AS (
    SELECT
        app_id,
        price_final AS previous_price
    FROM steam.games
    WHERE price_final > 0
      AND user_reviews IS NOT NULL
    ORDER BY user_reviews DESC, app_id ASC
    LIMIT 10
)
UPDATE steam.games AS g
SET price_final = ROUND(g.price_final * 0.90, 2)
FROM targets AS t
WHERE g.app_id = t.app_id
RETURNING
    g.app_id,
    g.title,
    t.previous_price,
    g.price_final AS simulated_price,
    10 AS campaign_discount_pct;
ROLLBACK;