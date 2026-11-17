BEGIN;

-- Birincil anahtarlar
ALTER TABLE customers      ADD PRIMARY KEY (customer_id);
ALTER TABLE orders         ADD PRIMARY KEY (order_id);
ALTER TABLE products       ADD PRIMARY KEY (product_id);
ALTER TABLE sellers        ADD PRIMARY KEY (seller_id);
ALTER TABLE order_items    ADD PRIMARY KEY (order_id, order_item_id);
ALTER TABLE order_payments ADD PRIMARY KEY (order_id, payment_sequential);

-- Yabancı anahtarlar (tablolar arası ilişkiler)
ALTER TABLE orders         ADD FOREIGN KEY (customer_id) REFERENCES customers;
ALTER TABLE order_items    ADD FOREIGN KEY (order_id)    REFERENCES orders;
ALTER TABLE order_items    ADD FOREIGN KEY (product_id)  REFERENCES products;
ALTER TABLE order_items    ADD FOREIGN KEY (seller_id)   REFERENCES sellers;
ALTER TABLE order_payments ADD FOREIGN KEY (order_id)    REFERENCES orders;
ALTER TABLE order_reviews  ADD FOREIGN KEY (order_id)    REFERENCES orders;

-- Ajanın kullanacağı salt okuma kullanıcısı
CREATE ROLE verisor_ro LOGIN PASSWORD 'ro_sifre_123';
GRANT CONNECT ON DATABASE olist TO verisor_ro;
GRANT USAGE ON SCHEMA public TO verisor_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO verisor_ro;
ALTER ROLE verisor_ro SET default_transaction_read_only = on;
ALTER ROLE verisor_ro SET statement_timeout = '5s';

COMMIT;
