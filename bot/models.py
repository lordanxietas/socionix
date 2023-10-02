from sqlalchemy import Column, String, Integer, select, MetaData, Table
from sqlalchemy import TIMESTAMP, VARCHAR, BOOLEAN, TEXT
from sqlalchemy import ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession
from sqlalchemy.orm import declarative_base, relationship, selectinload, sessionmaker
from sqlalchemy import select, delete
from sqlalchemy.sql.expression import func

from config import *

import asyncio

Base = declarative_base()

async def create_engine ():
    return create_async_engine(DATABASE_URL, echo=False)

async def create_session ():
    return AsyncSession(await create_engine())

class BaseModel(Base):
    __abstract__ = True
    id           = Column(Integer, nullable=False, unique=True, primary_key=True, autoincrement=True)

class User(BaseModel):
    __tablename__ = 'users'
    tgid       = Column(VARCHAR(255), nullable=False)

class Psychotype4D(BaseModel):
    __tablename__ = 'psychotypes4d'
    sociocod   = Column(VARCHAR(255), nullable=False)
    charatercod= Column(TEXT, nullable=False)
    first      = Column(ForeignKey('functions.id'), nullable=False)
    second     = Column(ForeignKey('functions.id'), nullable=False)

class Function (BaseModel):
    __tablename__ = 'functions'
    name       = Column(VARCHAR(255), nullable=False)

class Question(BaseModel):
    __tablename__ = 'questions'
    text       = Column(TEXT, nullable=False)
    to_func    = Column(ForeignKey('functions.id'))

async def questions_count():
    session = await create_session()
    count = (await session.execute(select(func.count(Question.id)))).scalar()
    await session.close()
    return count

class TestPassing(BaseModel):
    __tablename__ = 'testpassings'
    user       = Column(ForeignKey('users.id'))
    result     = Column(ForeignKey('psychotypes4d.id'), nullable=True)

    async def answered_count(self, function=None):
        if function == None:
            session = await create_session()
            count = (await session.execute(select(func.count(Answer.id)).where(Answer.test_pass == self.id))).scalar()
            await session.close()
            return count
        else:
            session = await create_session()

            count = (await session.execute(select(func.count(Answer.id)).where(
                Answer.test_pass == self.id, Answer.answer == True, Answer.question.in_(
                    select(Question.id).where(Question.to_func == function.id)
                )))).scalar()
            await session.close()
            return count

class Answer(BaseModel):
    __tablename__ = 'answers'
    test_pass  = Column(ForeignKey('testpassings.id'))
    testpassing= relationship('TestPassing', foreign_keys=[test_pass])
    question   = Column(ForeignKey('questions.id'))
    answer     = Column(BOOLEAN, nullable=False)

async def testpassings_count(user):
    session = await create_session()

    count = (await session.execute(select(func.count(TestPassing.id)).where(TestPassing.user == user.id))).scalar()

    await session.close()

    return count

