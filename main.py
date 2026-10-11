import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config import settings
from database import Database
from keyboards import (
    get_main_menu,
    get_catalog_keyboard,
    get_product_detail_keyboard,
    get_cart_keyboard,
    get_request_phone_keyboard,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=settings.bot_token)
dp = Dispatcher()
db = Database(settings.database_path)


class CheckoutState(StatesGroup):
    waiting_for_phone = State()


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "👋 **Добро пожаловать в наш онлайн-магазин!**\n\n"
        "Выберите раздел в меню ниже, чтобы ознакомиться с товарами или оформить заказ.",
        reply_markup=get_main_menu(),
        parse_mode="Markdown",
    )


@dp.message(F.text == "🛍 Каталог товаров")
async def show_catalog_msg(message: Message) -> None:
    products = await db.get_products()
    await message.answer(
        "📦 **Каталог доступных товаров:**\nВыберите товар для просмотра деталей и добавления в корзину:",
        reply_markup=get_catalog_keyboard(products),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "back_to_catalog")
async def back_to_catalog_cb(callback: CallbackQuery) -> None:
    products = await db.get_products()
    if callback.message:
        await callback.message.edit_text(
            "📦 **Каталог доступных товаров:**\nВыберите товар:",
            reply_markup=get_catalog_keyboard(products),
            parse_mode="Markdown",
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("prod_"))
async def show_product_detail(callback: CallbackQuery) -> None:
    assert callback.data is not None
    product_id = int(callback.data.split("_")[1])
    product = await db.get_product(product_id)

    if not product:
        await callback.answer("Товар не найден!", show_alert=True)
        return

    _, title, desc, price = product
    text = (
        f"🏷 **{title}**\n\n"
        f"📝 {desc}\n\n"
        f"💰 **Цена:** {price:,} ₽"
    )
    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=get_product_detail_keyboard(product_id),
            parse_mode="Markdown",
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def add_product_to_cart(callback: CallbackQuery) -> None:
    assert callback.data is not None
    product_id = int(callback.data.split("_")[1])
    await db.add_to_cart(user_id=callback.from_user.id, product_id=product_id)
    await callback.answer("✅ Товар успешно добавлен в корзину!")


@dp.message(F.text == "🛒 Корзина")
async def show_cart_msg(message: Message) -> None:
    cart_items = await db.get_cart(message.from_user.id)
    if not cart_items:
        await message.answer("🛒 Ваша корзина сейчас пуста.", reply_markup=get_cart_keyboard(has_items=False))
        return

    text_lines = ["🛒 **Ваша корзина:**\n"]
    total = 0
    for idx, (_, title, price, qty) in enumerate(cart_items, 1):
        subtotal = price * qty
        total += subtotal
        text_lines.append(f"{idx}. **{title}** — {qty} шт. × {price:,} ₽ = **{subtotal:,} ₽**")

    text_lines.append(f"\n💵 **Итого к оплате:** {total:,} ₽")
    await message.answer("\n".join(text_lines), reply_markup=get_cart_keyboard(has_items=True), parse_mode="Markdown")


@dp.callback_query(F.data == "clear_cart")
async def clear_cart_cb(callback: CallbackQuery) -> None:
    await db.clear_cart(callback.from_user.id)
    if callback.message:
        await callback.message.edit_text("🛒 Корзина очищена.", reply_markup=get_cart_keyboard(has_items=False))
    await callback.answer("Корзина очищена")


@dp.callback_query(F.data == "checkout")
async def checkout_start_cb(callback: CallbackQuery, state: FSMContext) -> None:
    cart_items = await db.get_cart(callback.from_user.id)
    if not cart_items:
        await callback.answer("Корзина пуста!", show_alert=True)
        return

    await state.set_state(CheckoutState.waiting_for_phone)
    if callback.message:
        await callback.message.answer(
            "📞 Для оформления заказа, пожалуйста, нажмите кнопку ниже или введите номер телефона сообщением:",
            reply_markup=get_request_phone_keyboard(),
        )
    await callback.answer()


@dp.message(CheckoutState.waiting_for_phone, F.text == "❌ Отмена")
async def checkout_cancel_msg(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Оформление заказа отменено.", reply_markup=get_main_menu())


@dp.message(CheckoutState.waiting_for_phone)
async def process_phone_and_finish_order(message: Message, state: FSMContext) -> None:
    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text.strip()
    else:
        await message.answer("Пожалуйста, отправьте контакт кнопкой или введите номер текстом.")
        return

    user = message.from_user
    cart_items = await db.get_cart(user.id)
    if not cart_items:
        await state.clear()
        await message.answer("Ваша корзина пуста. Нечего оформлять.", reply_markup=get_main_menu())
        return

    order_id = await db.create_order(
        user_id=user.id,
        user_name=user.full_name,
        user_username=user.username,
        phone=phone,
        cart_items=cart_items,
    )
    await state.clear()

    total = sum(price * qty for _, _, price, qty in cart_items)

    # Success confirmation to user
    await message.answer(
        f"🎉 **Заказ #{order_id} успешно оформлен!**\n\n"
        f"Сумма: **{total:,} ₽**\n"
        f"Наш менеджер свяжется с вами по номеру `{phone}` для подтверждения доставки.",
        reply_markup=get_main_menu(),
        parse_mode="Markdown",
    )

    # Notify admin
    items_summary = "\n".join([f"• {title} × {qty} шт. = {price * qty:,} ₽" for _, title, price, qty in cart_items])
    admin_text = (
        f"🚨 **НОВЫЙ ЗАКАЗ #{order_id}**\n\n"
        f"👤 Клиент: {user.full_name} (@{user.username or 'нет'})\n"
        f"📱 Телефон: `{phone}`\n"
        f"🆔 User ID: `{user.id}`\n\n"
        f"📦 **Состав заказа:**\n{items_summary}\n\n"
        f"💰 **Итого:** {total:,} ₽"
    )

    try:
        await bot.send_message(chat_id=settings.admin_id, text=admin_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to notify admin {settings.admin_id}: {e}")


@dp.message(F.text == "ℹ️ О магазине")
async def about_us_msg(message: Message) -> None:
    await message.answer(
        "☕️ **Coffee & Lifestyle Store**\n\n"
        "Мы поставляем отборный свежеобжаренный кофе и аксессуары.\n"
        "🚚 Быстрая доставка курьером по городу и СДЭК по РФ.\n"
        "⭐️ Гарантия качества на всю продукцию.",
        parse_mode="Markdown",
    )


@dp.message(F.text == "📞 Поддержка")
async def support_msg(message: Message) -> None:
    await message.answer(
        "💬 Возникли вопросы по заказу или оплате?\n"
        "Напишите нашему менеджеру: @manager_support\n"
        "График работы: Пн-Вс с 09:00 до 21:00.",
        parse_mode="Markdown",
    )


async def main() -> None:
    await db.init()
    logger.info("Database initialized successfully.")
    logger.info("Bot starting polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
