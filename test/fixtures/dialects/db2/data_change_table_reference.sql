SELECT id FROM FINAL TABLE (
    INSERT INTO orders (customer_id, amount) VALUES (42, 100)
);

SELECT changed.id FROM NEW TABLE (
    INSERT INTO "sales"."archive_orders" (id, amount)
    SELECT id, amount FROM orders WHERE amount > 100
) AS changed;

SELECT * FROM FINAL TABLE (
    UPDATE orders SET amount = amount + 10 WHERE customer_id = 42
) WHERE amount > 100 ORDER BY id;

SELECT id, amount FROM NEW TABLE (
    UPDATE orders SET amount = 200 WHERE id = 1
) changed;

SELECT previous.id, previous.amount FROM OLD TABLE (
    UPDATE orders SET amount = 300 WHERE id = 2
) AS previous;

select * from old table (
    delete from orders where amount = 0
);

WITH inserted AS (
    SELECT changed.order_id FROM FINAL TABLE (
        INSERT INTO orders (customer_id, amount) VALUES (42, 100), (43, 200)
    ) AS changed (order_id, customer_id, amount)
)
SELECT order_id FROM inserted ORDER BY order_id;
