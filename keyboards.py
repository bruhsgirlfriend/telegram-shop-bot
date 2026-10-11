from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Tuple


def get_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Каталог товаров"), KeyboardButton(text="🛒 Корзина")],
            [KeyboardButton(text="ℹ️ О магазине"), KeyboardButton(text="📞 Поддержка")],
        ],
        resize_keyboard=True,
    )


def get_catalog_keyboard(products: List[Tuple[int, str, str, int]]) -> InlineKeyboardMarkup:
    buttons = []
    for prod_id, title, _, price in products:
        buttons.append([InlineKeyboardButton(text=f"{title} — {price} ₽", callback_data=f"prod_{prod_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_product_detail_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ В корзину", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton(text="◀️ Назад в каталог", callback_data="back_to_catalog")],
        ]
    )


def get_cart_keyboard(has_items: bool) -> InlineKeyboardMarkup:
    if not has_items:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛍 Перейти в каталог", callback_data="back_to_catalog")]
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
            [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
            [InlineKeyboardButton(text="🛍 Продолжить покупки", callback_data="back_to_catalog")],
        ]
    )


def get_request_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
