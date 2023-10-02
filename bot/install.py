from models import *
import asyncio
import random

async def main() -> None:

    session = await create_session()

    if (await session.execute(select(Function.id))).scalars().first() != None:

        await session.close()
        print('[УСТАНОВКА] Выполнена')
        exit()
    
    

    with open('data/psychotypes_3d.txt') as f:
        new_3d = []
        psychotypes = f.read().split('\n')
        for psychotype in psychotypes:
            new_3d += [Function(
                name=psychotype
            )]

        session.add_all(new_3d)
        await session.commit()
    print('[УСТАНОВКА] Психотипы 3D установлены в базу данных')
    with open('data/psy.txt') as f:
        psychotypes = f.read().split('\n')
        new_4d = []
        for psychotype in psychotypes:
            p = psychotype.split(':')
            first = (await session.execute(select(Function).where(Function.name==p[0]))).scalars().first().id
            second= (await session.execute(select(Function).where(Function.name==p[1]))).scalars().first().id
            sociocod= p[2]
            charatercod=p[3]
            new_4d += [Psychotype4D(
                first=first,
                second=second,
                sociocod=sociocod,
                charatercod=charatercod
            )]
        session.add_all(new_4d)
        await session.commit()
    print('[УСТАНОВКА] Психотипы 4D установлены в базу данных')
    with open('data/questions.txt') as f:
        contents = f.read().split('\n')
        questions = []

        random.shuffle(contents)

        for question in contents:
            function, text = question.split(':')
            questions += [Question(
                text=text,
                to_func=(await session.execute(select(Function).where(Function.name==function))).scalars().first().id
            )]

        session.add_all(questions)
        await session.commit()
    print('[УСТАНОВКА] Вопросы установлены в базу данных')
    print('[УСТАНОВКА] Завершена')
asyncio.run(main())







