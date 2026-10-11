import aiosqlite
from typing import List, Optional, Tuple


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    price INTEGER NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cart (
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (user_id, product_id),
                    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_name TEXT,
                    user_username TEXT,
                    phone TEXT,
                    total_amount INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'created',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_title TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
                )
                """
            )

            # Seed default products if empty
            cursor = await db.execute("SELECT COUNT(*) FROM products")
            count = (await cursor.fetchone())[0]
            if count == 0:
                demo_items = [
                    ("Кофе зерновой Premium (1 кг)", "100% арабика свежей обжарки с нотами шоколада и орехов.", 1600),
                    ("Чай листовой Эрл Грей (250 г)", "Черный классический чай с бергамотом премиум качества.", 650),
                    ("Термокружка 500 мл", "Сохраняет тепло до 8 часов. Нержавеющая сталь, герметичная крышка.", 1200),
                    ("Круассан с миндалем (3 шт)", "Свежая выпечка из натурального сливочного масла.", 450),
                ]
                await db.executemany(
                    "INSERT INTO products (title, description, price) VALUES (?, ?, ?)",
                    demo_items,
                )
            await db.commit()

    async def get_products(self) -> List[Tuple[int, str, str, int]]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT id, title, description, price FROM products ORDER BY id ASC")
            return await cursor.fetchall()

    async def get_product(self, product_id: int) -> Optional[Tuple[int, str, str, int]]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT id, title, description, price FROM products WHERE id = ?", (product_id,))
            return await cursor.fetchone()

    async def add_to_cart(self, user_id: int, product_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO cart (user_id, product_id, quantity)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1
                """,
                (user_id, product_id),
            )
            await db.commit()

    async def get_cart(self, user_id: int) -> List[Tuple[int, str, int, int]]:
        """Returns: list of (product_id, title, price, quantity)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT p.id, p.title, p.price, c.quantity
                FROM cart c
                JOIN products p ON c.product_id = p.id
                WHERE c.user_id = ?
                """,
                (user_id,),
            )
            return await cursor.fetchall()

    async def clear_cart(self, user_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
            await db.commit()

    async def create_order(
        self,
        user_id: int,
        user_name: str,
        user_username: Optional[str],
        phone: str,
        cart_items: List[Tuple[int, str, int, int]],
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            total_amount = sum(item[2] * item[3] for item in cart_items)
            cursor = await db.execute(
                """
                INSERT INTO orders (user_id, user_name, user_username, phone, total_amount, status)
                VALUES (?, ?, ?, ?, ?, 'created')
                """,
                (user_id, user_name, user_username, phone, total_amount),
            )
            order_id = cursor.lastrowid
            assert order_id is not None

            order_items_data = [
                (order_id, title, price, quantity)
                for (_, title, price, quantity) in cart_items
            ]
            await db.executemany(
                """
                INSERT INTO order_items (order_id, product_title, price, quantity)
                VALUES (?, ?, ?, ?)
                """,
                order_items_data,
            )
            await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
            await db.commit()
            return order_id
