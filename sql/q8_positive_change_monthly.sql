WITH monthly AS (
    SELECT DATE_TRUNC('month', review_date)::DATE AS review_month,
           COUNT(*) AS total_reviews,
           COUNT(*) FILTER (WHERE is_recommended IS TRUE) AS positive_reviews
    FROM steam.recommendations
    WHERE review_date IS NOT NULL
      AND is_recommended IS NOT NULL
    GROUP BY DATE_TRUNC('month', review_date)::DATE
), rates AS (
    SELECT review_month, total_reviews, positive_reviews,
           100.0 * positive_reviews / NULLIF(total_reviews, 0) AS positive_pct
    FROM monthly
), comparison AS (
    SELECT review_month, total_reviews, positive_reviews, positive_pct,
           LAG(positive_pct) OVER (ORDER BY review_month) AS previous_month_pct
    FROM rates
)
SELECT review_month, total_reviews, positive_reviews,
       ROUND(positive_pct, 2) AS positive_pct,
       ROUND(previous_month_pct, 2) AS previous_month_pct,
       ROUND(positive_pct - previous_month_pct, 2) AS change_percentage_points
FROM comparison
ORDER BY review_month;