import asyncio
import logging
import sys

from config import BOT_TOKEN

from aiogram import Bot, Dispatcher, Router, BaseMiddleware, types as aiotypes
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F
from aiogram.handlers.callback_query import CallbackQuery

from typing import Callable, Dict, Any, Awaitable

from models import *

from aiogram.filters.callback_data import CallbackData

class StartPassingCallbackData(CallbackData, prefix='startpassing'):
    passingid: int
    act: str
    answer: str
    question_id: int

class PassingCallbackData(CallbackData, prefix='passing'):
    passingid: int
    act: str

async def login(event):
    session = await create_session()
    users = (await session.execute(select(func.count(User.id)).where(User.tgid == str(event.from_user.id))))
    if users.scalar() == 0:
        new_user = User(
            tgid=str(event.from_user.id)
        )
        session.add_all([new_user])
        await session.commit()

    result = await session.execute(select(User).where(User.tgid == str(event.from_user.id)))
    user = result.scalars().first()
    await session.close()
    return user


from aiogram import Router

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
r   = Router()

@r.message(CommandStart())
async def start_command_handler(message: aiotypes.Message):
    
    builder = InlineKeyboardBuilder()
    builder.row(
        aiotypes.InlineKeyboardButton(
            text="Пройти тест",
            callback_data=StartPassingCallbackData(
                passingid=0, act='start_passing', answer='None', question_id=0
            ).pack()
        )
    )
    await message.delete()
    await message.answer('''Добро пожаловать в бота для определения соционического типа.

Вы можете бесплатно типироваться здесь с точностью до 99%''', reply_markup=builder.as_markup())



@r.callback_query(StartPassingCallbackData.filter(F.act == 'start_passing'))
async def startpassing_next_question(query, callback_data):

    session = await create_session()
    user = await login(query)
    if callback_data.passingid == 0:
        
        if await testpassings_count(user) >= 5:
            await query.answer('Нельзя создать больше 5 прохождений')
            await profile(query)
            return
        else:
            test_passing = TestPassing(
                user=user.id,
                result=None
            )
            session.add_all([test_passing])
            await session.commit()
            await session.refresh(test_passing)
    else:
        test_passing = (await session.execute(select(TestPassing).where(TestPassing.id == callback_data.passingid))).scalars().first()

    if callback_data.question_id != 0 and callback_data.answer != 'None':
        #Выставляем ответ на вопрос
        new_answer = Answer(
            answer=True if callback_data.answer == 'yes' else False,
            question=callback_data.question_id,
            test_pass=test_passing.id
        )

        session.add_all([new_answer])
        await session.commit()
    await session.refresh(test_passing)
    #Берём самый последний ответ по TestPassing
    last_answer = (await session.execute(select(Answer).where(Answer.test_pass == test_passing.id).order_by(Answer.id.desc()))).scalars().first()

    if last_answer != None:
    #Берём следующий id относительно последнего отвеченного вопроса
        next_question_id = last_answer.question + 1
        exists = (await session.execute(select(func.count(Question.id)).where(Question.id == next_question_id))).scalar()
        if exists != 0:
            question = (await session.execute(select(Question).where(Question.id == next_question_id))).scalars().first()
        else:
            #Прохождение закончено
            await passing_result(query, callback_data)
            return
    else:
        #Берём самый первый вопрос
        question = (await session.execute(select(Question).order_by(Question.id))).scalars().first()

    builder = InlineKeyboardBuilder()
    builder.row(
        aiotypes.InlineKeyboardButton(text="Да", callback_data=StartPassingCallbackData(passingid=test_passing.id, act='start_passing', answer='yes', question_id=question.id).pack()),
        aiotypes.InlineKeyboardButton(text="Нет", callback_data=StartPassingCallbackData(passingid=test_passing.id, act='start_passing', answer='no', question_id=question.id).pack())
    )
    builder.row(
        aiotypes.InlineKeyboardButton(text=f"Приостановить прохождение #{test_passing.id}", callback_data='test_passings')
    )

    await session.close()

    await query.message.edit_text(f'''Вопрос {(await test_passing.answered_count())+1}/{await questions_count()}. Лучший тест по определению соционического типа в телеграм.

<b>{question.text}</b>''', reply_markup=builder.as_markup(), parse_mode="HTML")

@r.callback_query(F.data == 'profile')
async def profile(callback):
    builder = InlineKeyboardBuilder()

    builder.row(
        aiotypes.InlineKeyboardButton(text="Мои прохождения", callback_data='test_passings')
    )

    user = await login(callback)
    session = await create_session()

    test_passings_count = (await session.execute(select(func.count(TestPassing.id)).where(TestPassing.user == user.id))).scalar()

    answers_count = (await session.execute(select(func.count(Answer.id)).where(Answer.test_pass.in_(select(
        TestPassing.id).where(TestPassing.user == user.id))))).scalar()

    await session.close()
    await callback.message.edit_text(f'''SOCIONIX - лучший тест на соционический тип в телеграм.

Мой профиль
Прохождений: {test_passings_count}
Отвечено вопросов: {answers_count}

Вопросы для настоящего теста заимствованы у российского учёного соционика Виктора Таланова.

Для обработки результатов теста используется метод анализа "Программная-творческая функции".
''', reply_markup=builder.as_markup())

@r.callback_query(F.data == 'test_passings')
async def test_passings(callback):
    user = await login(callback)
    session = await create_session()
    test_passings = (await session.execute(select(TestPassing).where(TestPassing.user == user.id).order_by(TestPassing.id.desc()).limit(5))).scalars()
    builder = InlineKeyboardBuilder()
    count_questions = await questions_count()
    for test_passing in test_passings:
        builder.row(
            aiotypes.InlineKeyboardButton(text=f"Прохождение #{test_passing.id}. Отвечено: {(await test_passing.answered_count())}/{count_questions}", callback_data=PassingCallbackData(passingid=test_passing.id, act='show').pack())
        )
    builder.row(
        aiotypes.InlineKeyboardButton(text="Новое прохождение",callback_data=StartPassingCallbackData(passingid=0, act='start_passing', answer='None', question_id=0).pack()),
        aiotypes.InlineKeyboardButton(text="Назад", callback_data='profile')
    )

    await session.close()

    await callback.message.edit_text(f'''Мои прохождения

Вы можете продолжить прохождение тестов в любой момент, когда захотите. Бот сохраняет результаты прохождения каждого теста. Максимальное количество прохождений: 5. Посмотреть информацию о прохождениях, удалить или продолжить прохождение вы можете нажав на прохождение ниже.
''', reply_markup=builder.as_markup())

@r.callback_query(PassingCallbackData.filter(F.act == 'show'))
async def passing_show(callback, callback_data):
    session = await create_session()

    test_passing = (await session.execute(select(TestPassing).where(TestPassing.id == callback_data.passingid))).scalars().first()

    

    builder = InlineKeyboardBuilder()
    count_questions = await questions_count()
    
    builder.row(
        aiotypes.InlineKeyboardButton(text="Продолжить", callback_data=StartPassingCallbackData(
            passingid=test_passing.id, act='start_passing', answer='None', question_id=0).pack()),
        aiotypes.InlineKeyboardButton(text="Удалить", callback_data=PassingCallbackData(passingid=test_passing.id, act='remove').pack())
    )
    builder.row(
        aiotypes.InlineKeyboardButton(text="Расчёт результата", callback_data=PassingCallbackData(passingid=test_passing.id, act='get_result').pack()),
        aiotypes.InlineKeyboardButton(text="Назад", callback_data='test_passings')
    )

    # testpassing_answers = (await session.execute(select(Answer).where(Answer.test_pass == test_passing.id))).scalars()

    # for answer in testpassing_answers:
    #     pass

    await session.close()

    await callback.message.edit_text(f'''Прохождение #{callback_data.passingid}

Отвечено: {(await test_passing.answered_count())}/{count_questions}
''', reply_markup=builder.as_markup())

@r.callback_query(PassingCallbackData.filter(F.act == 'remove'))
async def passing_remove(callback, callback_data):

    user = await login(callback)

    session = await create_session()

    (await session.execute(delete(Answer).where(Answer.test_pass == callback_data.passingid)))
    (await session.execute(delete(TestPassing).where(TestPassing.id == callback_data.passingid)))

    await session.commit()

    await session.close()
    await callback.answer('Прохождение успешно удалено')
    await test_passings(callback)

@r.callback_query(PassingCallbackData.filter(F.act == 'get_result'))
async def passing_result(callback, callback_data):
    builder = InlineKeyboardBuilder()
    
    builder.row(
        aiotypes.InlineKeyboardButton(text="Назад", callback_data=PassingCallbackData(passingid=callback_data.passingid, act='show').pack())
    )

    session = await create_session()

    test_passing = (await session.execute(select(TestPassing).where(TestPassing.id == callback_data.passingid))).scalars().first()
    result = ''

    if await test_passing.answered_count() < 320:
        await callback.message.edit_text('Вы не ответили на все вопросы в прохождении. Невозможно рассчитать результат',
                                      reply_markup=builder.as_markup())


    nabor = {}
    for func_ in (await session.execute(select(Function))).scalars():
        count = await test_passing.answered_count(function=func_)
        result += f'{func_.name}:{(count)}\n'
        nabor[func_.name] = count

    res = {
        'ЧС': nabor['ЧС-програм']+nabor['ЧС-творч'],
        'БС': nabor['БС-програм']+nabor['БС-творч'],
        'ЧИ': nabor['ЧИ-програм']+nabor['ЧИ-творч'],
        'БИ': nabor['БИ-програм']+nabor['БИ-творч'],
        'ЧЛ': nabor['ЧЛ-програм']+nabor['ЧЛ-творч'],
        'БЛ': nabor['БЛ-програм']+nabor['БЛ-творч'],
        'ЧЭ': nabor['ЧЭ-програм']+nabor['ЧЭ-творч'],
        'БЭ': nabor['БЭ-програм']+nabor['БЭ-творч']
    }

    if nabor['ЧС-програм']+nabor['ЧС-творч'] > nabor['БС-програм']+nabor['БС-творч']:
        res['ЧС'] += 1
        res['БС'] -= 1
    elif nabor['ЧС-програм']+nabor['ЧС-творч'] < nabor['БС-програм']+nabor['БС-творч']:
        res['ЧС'] -= 1
        res['БС'] += 1

    if nabor['ЧЛ-програм']+nabor['ЧЛ-творч'] > nabor['БЛ-програм']+nabor['БЛ-творч']:
        res['ЧЛ'] += 1
        res['БЛ'] -= 1
    elif nabor['ЧЛ-програм']+nabor['ЧЛ-творч'] < nabor['БЛ-програм']+nabor['БЛ-творч']:
        res['ЧЛ'] -= 1
        res['БЛ'] += 1
    
    if nabor['ЧИ-програм']+nabor['ЧИ-творч'] > nabor['БИ-програм']+nabor['БИ-творч']:
        res['ЧИ'] += 1
        res['БИ'] -= 1
    elif nabor['ЧИ-програм']+nabor['ЧИ-творч'] < nabor['БИ-програм']+nabor['БИ-творч']:
        res['ЧИ'] -= 1
        res['БИ'] += 1
    
    if nabor['ЧЭ-програм']+nabor['ЧЭ-творч'] > nabor['БЭ-програм']+nabor['БЭ-творч']:
        res['ЧЭ'] += 1
        res['БЭ'] -= 1
    elif nabor['ЧЭ-програм']+nabor['ЧЭ-творч'] < nabor['БЭ-програм']+nabor['БЭ-творч']:
        res['ЧЭ'] -= 1
        res['БЭ'] += 1
    
    next_res = dict(res)

    #ЧС

    if res['ЧС']>res['ЧЛ']:
        next_res['ЧС'] += 1
        next_res['ЧЛ'] -= 1
    elif res['ЧС']<res['ЧЛ']:
        next_res['ЧС'] -= 1
        next_res['ЧЛ'] += 1

    if res['ЧС']>res['БЛ']:
        next_res['ЧС'] += 1
        next_res['БЛ'] -= 1
    elif res['ЧС']<res['БЛ']:
        next_res['ЧС'] -= 1
        next_res['БЛ'] += 1
    
    if res['ЧС']>res['ЧИ']:
        next_res['ЧС'] += 1
        next_res['ЧИ'] -= 1
    elif res['ЧС']<res['ЧИ']:
        next_res['ЧС'] -= 1
        next_res['ЧИ'] += 1
    
    if res['ЧС']>res['БИ']:
        next_res['ЧС'] += 1
        next_res['БИ'] -= 1
    elif res['ЧС']<res['БИ']:
        next_res['ЧС'] -= 1
        next_res['БИ'] += 1
    
    if res['ЧС']>res['ЧЭ']:
        next_res['ЧС'] += 1
        next_res['ЧЭ'] -= 1
    elif res['ЧС']<res['ЧЭ']:
        next_res['ЧС'] -= 1
        next_res['ЧЭ'] += 1
    
    if res['ЧС']>res['БЭ']:
        next_res['ЧС'] += 1
        next_res['БЭ'] -= 1
    elif res['ЧС']<res['БЭ']:
        next_res['ЧС'] -= 1
        next_res['БЭ'] += 1

    #БС

    if res['БС']>res['ЧЛ']:
        next_res['БС'] += 1
        next_res['ЧЛ'] -= 1
    elif res['БС']<res['ЧЛ']:
        next_res['БС'] -= 1
        next_res['ЧЛ'] += 1
    
    if res['БС']>res['БЛ']:
        next_res['БС'] += 1
        next_res['БЛ'] -= 1
    elif res['БС']<res['БЛ']:
        next_res['БС'] -= 1
        next_res['БЛ'] += 1
    
    if res['БС']>res['ЧИ']:
        next_res['БС'] += 1
        next_res['ЧИ'] -= 1
    elif res['БС']<res['ЧИ']:
        next_res['БС'] -= 1
        next_res['ЧИ'] += 1
    
    if res['БС']>res['БИ']:
        next_res['БС'] += 1
        next_res['БИ'] -= 1
    elif res['БС']<res['БИ']:
        next_res['БС'] -= 1
        next_res['БИ'] += 1

    if res['БС']>res['БЭ']:
        next_res['БС'] += 1
        next_res['БЭ'] -= 1
    elif res['БС']<res['БЭ']:
        next_res['БС'] -= 1
        next_res['БЭ'] += 1

    if res['БС']>res['ЧЭ']:
        next_res['БС'] += 1
        next_res['ЧЭ'] -= 1
    elif res['БС']<res['ЧЭ']:
        next_res['БС'] -= 1
        next_res['ЧЭ'] += 1

    #ЧЭ

    if res['ЧЭ']>res['ЧЛ']:
        next_res['ЧЭ'] += 1
        next_res['ЧЛ'] -= 1
    elif res['ЧЭ']<res['ЧЛ']:
        next_res['ЧЭ'] -= 1
        next_res['ЧЛ'] += 1
    
    if res['ЧЭ']>res['БЛ']:
        next_res['БЛ'] -= 1
        next_res['ЧЭ'] += 1
    elif res['ЧЭ']<res['БЛ']:
        next_res['ЧЭ'] -= 1
        next_res['БЛ'] += 1
    
    if res['ЧЭ']>res['ЧИ']:
        next_res['ЧЭ'] += 1
        next_res['ЧИ'] -= 1
    elif res['ЧЭ']<res['ЧИ']:
        next_res['ЧЭ'] -= 1
        next_res['ЧИ'] += 1
    
    if res['ЧЭ']>res['БИ']:
        next_res['ЧЭ'] += 1
        next_res['БИ'] -= 1
    elif res['ЧЭ']<res['БИ']:
        next_res['ЧЭ'] -= 1
        next_res['БИ'] += 1
    
    if res['ЧЭ']>res['ЧС']:
        next_res['ЧЭ'] += 1
        next_res['ЧС'] -= 1
    elif res['ЧЭ']<res['ЧС']:
        next_res['ЧЭ'] -= 1
        next_res['ЧС'] += 1
    
    if res['ЧЭ']>res['БС']:
        next_res['ЧЭ'] += 1
        next_res['БС'] -= 1
    elif res['ЧЭ']<res['БС']:
        next_res['ЧЭ'] -= 1
        next_res['БС'] += 1


    #БЭ
    if res['БЭ']>res['ЧЛ']:
        next_res['БЭ'] += 1
        next_res['ЧЛ'] -= 1
    elif res['БЭ']<res['ЧЛ']:
        next_res['БЭ'] -= 1
        next_res['ЧЛ'] += 1
    
    if res['БЭ']>res['БЛ']:
        next_res['БЭ'] += 1
        next_res['БЛ'] -= 1
    elif res['БЭ']<res['БЛ']:
        next_res['БЭ'] -= 1
        next_res['БЛ'] += 1
    
    if res['БЭ']>res['ЧИ']:
        next_res['БЭ'] += 1
        next_res['ЧИ'] -= 1
    elif res['БЭ']<res['ЧИ']:
        next_res['БЭ'] -= 1
        next_res['ЧИ'] += 1
    
    if res['БЭ']>res['БИ']:
        next_res['БЭ'] += 1
        next_res['БИ'] -= 1
    elif res['БЭ']<res['БИ']:
        next_res['БЭ'] -= 1
        next_res['БИ'] += 1
    
    if res['БЭ']>res['ЧС']:
        next_res['БЭ'] += 1
        next_res['ЧС'] -= 1
    elif res['БЭ']<res['ЧС']:
        next_res['БЭ'] -= 1
        next_res['ЧС'] += 1
    
    if res['БЭ']>res['БС']:
        next_res['БЭ'] += 1
        next_res['БС'] -= 1
    elif res['БЭ']<res['БС']:
        next_res['БЭ'] -= 1
        next_res['БС'] += 1

    


    #ЧЛ
    if res['ЧЛ']>res['ЧЭ']:
        next_res['ЧЛ'] += 1
        next_res['ЧЭ'] -= 1
    elif res['ЧЛ']<res['ЧЭ']:
        next_res['ЧЛ'] -= 1
        next_res['ЧЭ'] += 1
    
    if res['ЧЛ']>res['БЭ']:
        next_res['ЧЛ'] += 1
        next_res['БЭ'] -= 1
    elif res['ЧЛ']<res['БЭ']:
        next_res['ЧЛ'] -= 1
        next_res['БЭ'] += 1
    
    if res['ЧЛ']>res['ЧИ']:
        next_res['ЧЛ'] += 1
        next_res['ЧИ'] -= 1
    elif res['ЧЛ']<res['ЧИ']:
        next_res['ЧЛ'] -= 1
        next_res['ЧИ'] += 1
    
    if res['ЧЛ']>res['БИ']:
        next_res['ЧЛ'] += 1
        next_res['БИ'] -= 1
    elif res['ЧЛ']<res['БИ']:
        next_res['ЧЛ'] -= 1
        next_res['БИ'] += 1
    
    if res['ЧЛ']>res['ЧС']:
        next_res['ЧЛ'] += 1
        next_res['ЧС'] -= 1
    elif res['ЧЛ']<res['ЧС']:
        next_res['ЧЛ'] -= 1
        next_res['ЧС'] += 1
    
    if res['ЧЛ']>res['БС']:
        next_res['ЧЛ'] += 1
        next_res['БС'] -= 1
    elif res['ЧЛ']<res['БС']:
        next_res['ЧЛ'] -= 1
        next_res['БС'] += 1



    #БЛ
    if res['БЛ']>res['ЧЭ']:
        next_res['БЛ'] += 1
        next_res['ЧЭ'] -= 1
    elif res['БЛ']<res['ЧЭ']:
        next_res['БЛ'] -= 1
        next_res['ЧЭ'] += 1
    
    if res['БЛ']>res['БЭ']:
        next_res['БЛ'] += 1
        next_res['БЭ'] -= 1
    elif res['БЛ']<res['БЭ']:
        next_res['БЛ'] -= 1
        next_res['БЭ'] += 1
    
    if res['БЛ']>res['ЧИ']:
        next_res['БЛ'] += 1
        next_res['ЧИ'] -= 1
    elif res['БЛ']<res['ЧИ']:
        next_res['БЛ'] -= 1
        next_res['ЧИ'] += 1
    
    if res['БЛ']>res['БИ']:
        next_res['БЛ'] += 1
        next_res['БИ'] -= 1
    elif res['БЛ']<res['БИ']:
        next_res['БЛ'] -= 1
        next_res['БИ'] += 1
    
    if res['БЛ']>res['ЧС']:
        next_res['БЛ'] += 1
        next_res['ЧС'] -= 1
    elif res['БЛ']<res['ЧС']:
        next_res['БЛ'] -= 1
        next_res['ЧС'] += 1
    
    if res['БЛ']>res['БС']:
        next_res['БЛ'] += 1
        next_res['БС'] -= 1
    elif res['БЛ']<res['БС']:
        next_res['БЛ'] -= 1
        next_res['БС'] += 1

    
    #ЧИ
    if res['ЧИ']>res['ЧЭ']:
        next_res['ЧИ'] += 1
        next_res['ЧЭ'] -= 1
    elif res['ЧИ']<res['ЧЭ']:
        next_res['ЧИ'] -= 1
        next_res['ЧЭ'] += 1
    
    if res['ЧИ']>res['БЭ']:
        next_res['ЧИ'] += 1
        next_res['БЭ'] -= 1
    elif res['ЧИ']<res['БЭ']:
        next_res['ЧИ'] -= 1
        next_res['БЭ'] += 1
    
    if res['ЧИ']>res['ЧЛ']:
        next_res['ЧИ'] += 1
        next_res['ЧЛ'] -= 1
    elif res['ЧИ']<res['ЧЛ']:
        next_res['ЧИ'] -= 1
        next_res['ЧЛ'] += 1
    
    if res['ЧИ']>res['БЛ']:
        next_res['ЧИ'] += 1
        next_res['БЛ'] -= 1
    elif res['ЧИ']<res['БЛ']:
        next_res['ЧИ'] -= 1
        next_res['БЛ'] += 1
    
    if res['ЧИ']>res['ЧС']:
        next_res['ЧИ'] += 1
        next_res['ЧС'] -= 1
    elif res['ЧИ']<res['ЧС']:
        next_res['ЧИ'] -= 1
        next_res['ЧС'] += 1
    
    if res['ЧИ']>res['БС']:
        next_res['ЧИ'] += 1
        next_res['БС'] -= 1
    elif res['ЧИ']<res['БС']:
        next_res['ЧИ'] -= 1
        next_res['БС'] += 1
    

    #БИ
    if res['БИ']>res['ЧЭ']:
        next_res['БИ'] += 1
        next_res['ЧЭ'] -= 1
    elif res['БИ']<res['ЧЭ']:
        next_res['БИ'] -= 1
        next_res['ЧЭ'] += 1
    
    if res['БИ']>res['БЭ']:
        next_res['БИ'] += 1
        next_res['БЭ'] -= 1
    elif res['БИ']<res['БЭ']:
        next_res['БИ'] -= 1
        next_res['БЭ'] += 1
    
    if res['БИ']>res['ЧЛ']:
        next_res['БИ'] += 1
        next_res['ЧЛ'] -= 1
    elif res['БИ']<res['ЧЛ']:
        next_res['БИ'] -= 1
        next_res['ЧЛ'] += 1
    
    if res['БИ']>res['БЛ']:
        next_res['БИ'] += 1
        next_res['БЛ'] -= 1
    elif res['БИ']<res['БЛ']:
        next_res['БИ'] -= 1
        next_res['БЛ'] += 1
    
    if res['БИ']>res['ЧС']:
        next_res['БИ'] += 1
        next_res['ЧС'] -= 1
    elif res['БИ']<res['ЧС']:
        next_res['БИ'] -= 1
        next_res['ЧС'] += 1
    
    if res['БИ']>res['БС']:
        next_res['БИ'] += 1
        next_res['БС'] -= 1
    elif res['БИ']<res['БС']:
        next_res['БИ'] -= 1
        next_res['БС'] += 1

    res = sorted(next_res.items(), key=lambda kv: kv[1], reverse=True)

    resultat = 'Ваш тип: '

    first = res[0][0]
    second= res[1][0]

    if first == 'ЧС' and second == 'ЧЛ':
        resultat += 'Эпилептоид паранойяльного типа - СЛЭ с акцентом на ЧЛ'
    elif first == 'ЧС' and second == 'БЛ':
        resultat += 'Эпилептоид ананкастного типа - СЛЭ с акцентом на БЛ'
    elif first == 'ЧС' and second == 'ЧЭ':
        resultat += 'Эпилептоид истероидного типа - СЭЭ с акцентом на ЧЭ'
    elif first == 'ЧС' and second == 'БЭ':
        resultat += 'Эпилептоид эмотивного типа - СЭЭ с акцентом на БЭ'
    elif first == 'ЧЛ' and second == 'ЧС':
        resultat += 'Паранойял эпилептоидного типа - ЛСЭ с акцентом на ЧС'
    elif first == 'ЧЛ' and second == 'БС':
        resultat += 'Паранойял нарциссического типа - ЛСЭ с акцентом на БС'
    elif first == 'ЧЛ' and second == 'ЧИ':
        resultat += 'Паранойял гипертимного типа - ЛИЭ с акцентом на ЧИ'
    elif first == 'ЧЛ' and second == 'БИ':
        resultat += 'Паранойял шизоидного типа - ЛИЭ с акцентом на БИ'
    elif first == 'БЛ' and second == 'ЧС':
        resultat += 'Ананкаст эпилептоидного типа - ЛСИ с акцентом на ЧС'
    elif first == 'БЛ' and second == 'БС':
        resultat += 'Ананкаст нарциссического типа - ЛСИ с акцентом на БС'
    elif first == 'БЛ' and second == 'ЧИ':
        resultat += 'Ананкаст гипертимного типа - ЛСИ с акцентом на ЧИ'
    elif first == 'БЛ' and second == 'БИ':
        resultat += 'Ананкаст шизоидного типа - ЛСИ с акцентом на БИ'
    elif first == 'ЧЭ' and second == 'ЧС':
        resultat += 'Истероид эпилептоидного типа - ЭСЭ с акцентом на ЧС'
    elif first == 'ЧЭ' and second == 'БС':
        resultat += 'Истероид нарциссического типа - ЭСЭ с акцентом на БС'
    elif first == 'ЧЭ' and second == 'ЧИ':
        resultat += 'Истероид гипертимного типа - ЭИЭ с акцентом на ЧИ'
    elif first == 'ЧЭ' and second == 'БИ':
        resultat += 'Истероид шизоидного типа - ЭИЭ с акцентом на БИ'
    elif first == 'БЭ' and second == 'ЧС':
        resultat += 'Эмотив эпилептоидного типа - ЭСИ с акцентом на ЧС'
    elif first == 'БЭ' and second == 'БС':
        resultat += 'Эмотив нарциссического типа - ЭСИ с акцентом на БС'
    elif first == 'БЭ' and second == 'ЧИ':
        resultat += 'Эмотив гипертимного типа - ЭИИ с акцентом на ЧИ'
    elif first == 'БЭ' and second == 'БИ':
        resultat += 'Эмотив шизоидного типа - ЭИИ с акцентом на БИ'
    elif first == 'БС' and second == 'ЧЛ':
        resultat += 'Нарцисс паранойяльного типа - СЛИ с акцентом на ЧЛ'
    elif first == 'БС' and second == 'БЛ':
        resultat += 'Нарцисс ананкастного типа - СЛИ с акцентом на БЛ'
    elif first == 'БС' and second == 'ЧЭ':
        resultat += 'Нарцисс истероидного типа - СЭИ с акцентом на ЧЭ'
    elif first == 'БС' and second == 'БЭ':
        resultat += 'Нарцисс эмотивного типа - СЭИ с акцентом на БЭ'
    elif first == 'БИ' and second == 'ЧЛ':
        resultat += 'Шизоид паранойяльного типа - ИЛИ с акцентом на ЧЛ'
    elif first == 'БИ' and second == 'БЛ':
        resultat += 'Шизоид ананкастного типа - ИЛИ с акцентом на БЛ'
    elif first == 'БИ' and second == 'ЧЭ':
        resultat += 'Шизоид истероидного типа - ИЭИ с акцентом на ЧЭ'
    elif first == 'БИ' and second == 'БЭ':
        resultat += 'Шизоид эмотивного типа - ИЭИ с акцентом на БЭ'
    elif first == 'ЧИ' and second == 'ЧЛ':
        resultat += 'Гипертим паранойяльного типа - ИЛЭ с акцентом на ЧЛ'
    elif first == 'ЧИ' and second == 'БЛ':
        resultat += 'Гипертим ананкастного типа - ИЛЭ с акцентом на БЛ'
    elif first == 'ЧИ' and second == 'ЧЭ':
        resultat += 'Гипертим истероидного типа - ИЭЭ с акцентом на ЧЭ'
    elif first == 'ЧИ' and second == 'БЭ':
        resultat += 'Гипертим эмотивного типа - ИЭЭ с акцентом на БЭ'
    else :
        resultat = f'В результате прохождения теста определить психотип невозможно. Программная функция: {first}, творческая функция: {second}'
    await session.close()
    await callback.message.edit_text(f'''Расчёт результата по прохождению #{test_passing.id}

{result}

{resultat}
''', reply_markup=builder.as_markup())

dp.include_router(r)