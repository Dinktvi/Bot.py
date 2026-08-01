from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    add_code = State()
    add_discount = State()
    broadcast = State()
    add_sponsor = State()
    add_auction = State()


class UserPromoStates(StatesGroup):
    enter_code = State()


class IdeaStates(StatesGroup):
    idea = State()


class ChatStates(StatesGroup):
    assistant = State()
    support = State()
