DROP TABLE IF EXISTS products;

CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL
);
ALTER TABLE products ADD COLUMN image TEXT;

INSERT INTO products (name, description, price, stock) VALUES
('Laptop Lenovo ThinkPad', 'Laptop empresarial de alto rendimiento', 18500.00, 12),
('Mouse Logitech M280', 'Mouse inalámbrico ergonómico', 350.00, 50),
('Teclado Mecánico Redragon', 'Teclado gaming retroiluminado', 1200.00, 25),
('Monitor Samsung 24\"', 'Monitor LED Full HD 24 pulgadas', 2900.00, 18),
('Audífonos Sony WH-CH510', 'Audífonos inalámbricos Bluetooth', 750.00, 30),
('Memoria USB Kingston 64GB', 'USB 3.0 de alta velocidad', 180.00, 100),
('Impresora HP DeskJet 2700', 'Impresora multifuncional WiFi', 1450.00, 10);
