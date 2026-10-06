-- BusinessIQ example queries (run with any SQLite client on database/businessiq.db)

-- 1. Revenue, orders and average order value per day
SELECT date(order_time) AS day, ROUND(SUM(sales_amount),0) AS revenue,
       COUNT(*) AS orders, ROUND(AVG(sales_amount),2) AS avg_order_value
FROM orders GROUP BY day ORDER BY day;

-- 2. Revenue by category (last 7 days)
SELECT item_type, ROUND(SUM(sales_amount),0) AS revenue, SUM(quantity) AS units
FROM v_orders WHERE order_time >= datetime('now','localtime','-7 days')
GROUP BY item_type ORDER BY revenue DESC;

-- 3. Busiest hours of the day
SELECT strftime('%H', order_time) AS hour, COUNT(*) AS orders
FROM orders GROUP BY hour ORDER BY hour;

-- 4. Outlet league table
SELECT outlet_identifier, outlet_type, outlet_location_type,
       ROUND(SUM(sales_amount),0) AS revenue, COUNT(*) AS orders
FROM v_orders GROUP BY outlet_identifier ORDER BY revenue DESC;

-- 5. Today vs yesterday, same elapsed time of day
SELECT
  ROUND(SUM(CASE WHEN date(order_time)=date('now','localtime') THEN sales_amount END),0) AS today,
  ROUND(SUM(CASE WHEN date(order_time)=date('now','localtime','-1 day')
                 AND time(order_time)<=time('now','localtime') THEN sales_amount END),0) AS yesterday_so_far
FROM orders;

-- 6. Top 10 products by revenue
SELECT item_identifier, item_type, ROUND(SUM(sales_amount),0) AS revenue
FROM v_orders GROUP BY item_identifier, item_type ORDER BY revenue DESC LIMIT 10;
