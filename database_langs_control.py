import asyncio
import numpy as np

import aiomysql
from aiomysql import connect
from deep_translator import GoogleTranslator
from pymysql import IntegrityError


reset = '\033[0m'
bold = '\033[01m'
disable = '\033[02m'
underline = '\033[04m'
reverse = '\033[07m'
strikethrough = '\033[09m'
invisible = '\033[08m'


class fg:
    black = '\033[30m'
    red = '\033[31m'
    green = '\033[32m'
    orange = '\033[33m'
    blue = '\033[34m'
    purple = '\033[35m'
    cyan = '\033[36m'
    lightgrey = '\033[37m'
    darkgrey = '\033[90m'
    lightred = '\033[91m'
    lightgreen = '\033[92m'
    yellow = '\033[93m'
    lightblue = '\033[94m'
    pink = '\033[95m'
    lightcyan = '\033[96m'


async def translate(text: str, sourcelang: str, targetlang: str):
    return GoogleTranslator(source=sourcelang, target=targetlang).translate(text)


# async def make_translations(text: str, source_lang_id: int, source_lang_code: str, source_gtrans_code: str, text_content_id: int, langs_list)


async def add_lang_names_translations(lang_list: list = None, lang_ids: list = None):
    async with connect(port=3306, user='root', password='velka2015', db='words_game_langs') as langs_conn, connect(
            port=3306, user='root', password='velka2015', db='words_game') as common_conn:
        async with langs_conn.cursor() as langs_cur, common_conn.cursor() as common_cur:
            if (lang_list is None) and (lang_ids is None):
                await langs_cur.execute(f'SELECT `id`, `lang_code`, `lang_gtrans_code`, `lang_name` FROM `languages`;')
                lang_list = list(await langs_cur.fetchall())
                lang_ids = np.asarray(lang_list)[:, 0].reshape(-1)
            elif (lang_list is not None) and (lang_ids is not None):
                pass
            else:
                raise AttributeError("`lang_list` and `lang_ids` can't be None separately")

            for lang_info, lang_id in zip(lang_list, lang_ids):
                lang_code = lang_info[1]
                lang_gtrans_code = lang_info[2]
                lang_name = lang_info[3]

                print(fg.yellow + f'** Adding language {lang_name} ({lang_code}) to TEXT_CONTENT... **' + reset)
                await common_cur.execute(f'SELECT * FROM `lang_name_texts` WHERE codename="{lang_code}"')
                if len(list(await common_cur.fetchall())) > 0:
                    print(fg.red + f'** Language {lang_name} ({lang_code}) already exists **' + reset)
                    continue

                await langs_cur.execute(
                    f'INSERT INTO `text_content` (original_text, original_lang_id) VALUES ("{lang_name}", "{lang_id}");')
                await langs_conn.commit()
                lang_text_content_id = langs_cur.lastrowid
                await common_cur.execute(
                    f'INSERT INTO `lang_name_texts` (codename, text_content_id) VALUES ("{lang_code}", "{lang_text_content_id}");')
                await common_conn.commit()

                await langs_cur.execute(
                    f'SELECT `id`,`lang_code`,`lang_gtrans_code` FROM `languages` WHERE id<>{lang_id}')
                existed_langs_list = list(await langs_cur.fetchall())
                translation_execute_str = f'INSERT INTO `translations` (translation, lang_id, text_content_id) VALUES '
                print(fg.orange + f'\t** Adding translations for {lang_name} ({lang_code})... **' + reset)
                try:
                    for existed_lang_info in existed_langs_list:
                        existed_lang_id = existed_lang_info[0]
                        existed_lang_code = existed_lang_info[1]
                        existed_lang_gtrans_code = existed_lang_info[2]
                        translated_text = await translate(lang_name, sourcelang=lang_gtrans_code,
                                                          targetlang=existed_lang_gtrans_code)
                        translated_text = translated_text[0].upper() + translated_text[1:]
                        print(f'\t{lang_code} -> {existed_lang_code}:')
                        print(f'\t\t{translated_text};')
                        translation_execute_str += f'("{translated_text}", "{existed_lang_id}", "{lang_text_content_id}"),'
                except Exception as e:
                    print(f'\t{e}')
                    print(fg.red + f'** Adding language {lang_name} ({lang_code}) FAILED... **' + reset)
                    await langs_cur.execute(
                        f'DELETE FROM `text_content` WHERE id={lang_text_content_id}')
                    await langs_conn.commit()
                    continue
                translation_execute_str = translation_execute_str[:-1] + ';'
                await langs_cur.execute(translation_execute_str)
                await langs_conn.commit()
            print(fg.green + '** Languages translations successfully added **' + reset)


async def add_languages(lang_list):
    added_lang_ids = list()
    async with connect(port=3306, user='root', password='velka2015', db='words_game_langs') as conn:
        async with conn.cursor() as cur:
            for lang_info in lang_list:
                lang_code = lang_info[0]
                lang_gtrans_code = lang_info[1]
                lang_name = lang_info[2]
                try:
                    await cur.execute(
                        f'INSERT INTO `languages` (lang_code, lang_gtrans_code, lang_name) VALUES ("{lang_code}", "{lang_gtrans_code}", "{lang_name}");')
                    await conn.commit()
                except IntegrityError:
                    print(fg.red + f'** Language {lang_name} ({lang_code}) already exists!**' + reset)
                    continue

                added_lang_id = cur.lastrowid

                await cur.execute(f'SELECT `id`, `original_text`, `original_lang_id` FROM `text_content`')
                all_text_content = list(await cur.fetchall())
                print(fg.yellow + f'** Language {lang_name} ({lang_code}) adding...**' + reset)
                if len(all_text_content) > 0:
                    translations_execute_str = f'INSERT INTO `translations` (translation, lang_id, text_content_id) VALUES '
                    try:
                        for text_content in all_text_content:
                            text_content_id = text_content[0]
                            original_text = text_content[1]
                            original_lang_id = text_content[2]
                            await cur.execute(
                                f'SELECT `lang_code`, `lang_gtrans_code` FROM `languages` WHERE id={original_lang_id}')
                            original_lang_info = await cur.fetchone()
                            original_lang_code = original_lang_info[0]
                            original_lang_gtrans_code = original_lang_info[1]
                            translations_execute_str += f'("{await translate(original_text, sourcelang=original_lang_gtrans_code, targetlang=lang_gtrans_code)}", "{added_lang_id}", "{text_content_id}"),'
                            print(
                                fg.green + f'\tTranslation for "{original_text}" {original_lang_code} -> {lang_code} DONE!' + reset)
                    except Exception as e:
                        print(f'\t{e}')
                        print(
                            fg.red + f'\tTranslation for "{original_text}" {original_lang_code} -> {lang_code} FAILED!' + reset)
                        await cur.execute(
                            f'DELETE FROM `languages` WHERE id={added_lang_id}')
                        await conn.commit()
                        lang_list.remove(lang_info)
                        continue
                    added_lang_ids.append(added_lang_id)
                    translations_execute_str = translations_execute_str[:-1] + ';'
                    await cur.execute(translations_execute_str)
                    await conn.commit()
                print(fg.green + f'** Language {lang_name} ({lang_code}) added **' + reset)
            print(fg.green + f'** Languages\n\t' +
                  ",\n\t".join(list(np.asarray(lang_list)[:, 2])) +
                  '\nsuccessfully added **' + reset)
    await add_lang_names_translations(lang_list=lang_list, lang_ids=added_lang_ids)


async def add_texts(texts: dict):
    async with connect(port=3306, user='root', password='velka2015', db='words_game') as com_con, connect(port=3306,
                                                                                                        user='root',
                                                                                                        password='velka2015',
                                                                                                        db='words_game_langs') as langs_con:
        async with com_con.cursor() as com_cur, langs_con.cursor() as langs_cur:
            added_content_count = 0
            for text_table_type in texts.keys():
                execute_str = f'INSERT INTO `{text_table_type}` (codename, text_content_id) VALUES '
                for codename, text in zip(texts[text_table_type].keys(), texts[text_table_type].values()):
                    await com_cur.execute(f'SELECT * FROM `{text_table_type}` WHERE codename="{codename}"')
                    if len(await com_cur.fetchall()) > 0:
                        print(fg.red + f'** Text "{text}" with codename "{codename}" already exists! **' + reset)
                        continue

                    await langs_cur.execute(f"INSERT INTO `text_content` (original_text) VALUES ('{text}')")
                    await langs_con.commit()
                    added_text_content_id = langs_cur.lastrowid

                    await langs_cur.execute(
                        f'SELECT `original_lang_id` FROM `text_content` WHERE id={added_text_content_id}')
                    original_lang_id = (await langs_cur.fetchone())[0]
                    await langs_cur.execute(f'SELECT `lang_gtrans_code` FROM `languages` WHERE id={original_lang_id}')
                    original_lang_gtrans_code = (await langs_cur.fetchone())[0]

                    translation_execute_str = f'INSERT INTO `translations` (translation, lang_id, text_content_id) VALUES '
                    await langs_cur.execute(
                        f'SELECT `id`,`lang_code`,`lang_gtrans_code` FROM `languages` WHERE id<>{original_lang_id}')

                    print(fg.yellow + f'** Translations for "{text}" **' + reset)
                    try:
                        for lang_info in list(await langs_cur.fetchall()):
                            lang_id = lang_info[0]
                            lang_code = lang_info[1]
                            lang_gtrans_code = lang_info[2]
                            translated_text = await translate(text, sourcelang=original_lang_gtrans_code,
                                                              targetlang=lang_gtrans_code)
                            print(f'\t{original_lang_gtrans_code} -> {lang_code}:')
                            print(f'\t\t{translated_text};')
                            translation_execute_str += f'("{translated_text}", "{lang_id}", "{added_text_content_id}"),'
                    except Exception as e:
                        print(f'\t{e}')
                        print(fg.red + f'** Translation process for "{text}" FAILED **' + reset)
                        await langs_cur.execute(f'DELETE FROM `text_content` WHERE id={added_text_content_id}')
                        await langs_con.commit()
                        continue
                    translation_execute_str = translation_execute_str[:-1] + ';'
                    execute_str += f'("{codename}", "{added_text_content_id}"),'
                    await langs_cur.execute(translation_execute_str)
                    await langs_con.commit()
                execute_str = execute_str[:-1] + ';'
                try:
                    await com_cur.execute(execute_str)
                    await com_con.commit()
                    added_content_count += 1
                except Exception:
                    pass
            if added_content_count > 0:
                print(fg.green + '** New words successfully added **' + reset)


async def edit_texts(texts: dict):
    async with connect(port=3306, user='root', password='velka2015', db='words_game') as com_con, connect(port=3306,
                                                                                                        user='root',
                                                                                                        password='velka2015',
                                                                                                        db='words_game_langs') as langs_con:
        async with com_con.cursor() as com_cur, langs_con.cursor() as langs_cur:
            added_content_count = 0
            for text_table_type in texts.keys():
                for codename, text in zip(texts[text_table_type].keys(), texts[text_table_type].values()):
                    await com_cur.execute(
                        f'SELECT text_content_id FROM `{text_table_type}` WHERE codename="{codename}"')
                    result = list(await com_cur.fetchone())
                    added_text_content_id = result[0]
                    if len(result) == 0:
                        print(fg.red + f'** Text "{text}" with codename "{codename}" does not exists! **' + reset)
                        continue

                    await langs_cur.execute(
                        f"UPDATE `text_content` SET original_text='{text}' WHERE id={added_text_content_id}")
                    await langs_con.commit()

                    await langs_cur.execute(
                        f'SELECT `original_lang_id` FROM `text_content` WHERE id={added_text_content_id}')
                    original_lang_id = (await langs_cur.fetchone())[0]
                    await langs_cur.execute(f'SELECT `lang_gtrans_code` FROM `languages` WHERE id={original_lang_id}')
                    original_lang_gtrans_code = (await langs_cur.fetchone())[0]

                    await langs_cur.execute(
                        f'SELECT `id`,`lang_code`,`lang_gtrans_code` FROM `languages` WHERE id<>{original_lang_id}')

                    print(fg.yellow + f'** Translations for "{text}" **' + reset)
                    for lang_info in list(await langs_cur.fetchall()):
                        lang_id = lang_info[0]
                        lang_code = lang_info[1]
                        lang_gtrans_code = lang_info[2]
                        translated_text = await translate(text, sourcelang=original_lang_gtrans_code,
                                                          targetlang=lang_gtrans_code)
                        print(f'\t{original_lang_gtrans_code} -> {lang_code}:')
                        print(f'\t\t{translated_text};')
                        await langs_cur.execute(
                            f"UPDATE `translations` SET translation='{translated_text}' WHERE text_content_id='{added_text_content_id}' AND lang_id='{lang_id}'")
                        await langs_con.commit()
                    added_content_count += 1
            if added_content_count > 0:
                print(fg.green + '** Words successfully edited **' + reset)


langs = [
    ['de', 'de', 'Deutsch'],
    ['en', 'en', 'English'],
    ['es', 'es', 'Español'],
    ['fr', 'fr', 'Français'],
    ['it', 'it', 'Italiano'],
    ['jp', 'ja', '日本'],
    ['kr', 'ko', '한국인'],
    ['pt', 'pt', 'Português'],
    ['ru', 'ru', 'Русский'],
    ['ua', 'uk', 'Український'],
]

# asyncio.run(add_languages(langs))
asyncio.run(add_texts(
    {
        'button_texts': {
            'new_game': 'Создать игровую комнату',
            'join_game': 'Присоединиться к игровой комнате',
            'rating': 'Рейтинг',
            'sign_in': 'Войти',
            'sign_up': 'Зарегистрироваться',
            'logout': 'Выйти'
        },
        'info_texts': {
            'now_online': 'Сейчас онлайн',
            'last_visit': 'Последний визит',
            'privileges': 'Привилегии',
            'about_user': 'О пользователе',
            'user_created': 'Создан',
            'room_created': 'Создана',
            '1_month': 'января',
            '2_month': 'февраля',
            '3_month': 'марта',
            '4_month': 'апреля',
            '5_month': 'мая',
            '6_month': 'июня',
            '7_month': 'июля',
            '8_month': 'августа',
            '9_month': 'сентября',
            '10_month': 'октября',
            '11_month': 'ноября',
            '12_month': 'декабря',
            'language': 'Язык:',
        },
        'privilege': {
            'user': 'Пользователь',
            'admin': 'Администратор',
            'bot': 'Искусственный разум',
        }
    }
))

# asyncio.run(add_texts(
#     {
#         'button_texts': {
#             'join_game': '{} Присоединиться к игре',
#             'user_profile': '{} Мой профиль',
#             'my_games': '{} Архив моих игр',
#             'group': '{} Группа',
#             'rating': '{} Рейтинг',
#             'group_info': '{} Инфо группы',
#             'back_to_groups': 'В меню выбора групп',
#             'no_groups': 'Нет игровых групп',
#             'nothing found': 'Ничего не найдено',
#             'donators_list': 'Список пожертвователей',
#             'popular_groups': '{} Популярные игровые группы',
#             'search_groups': '{} Поиск игровых группы',
#             'enter_group_by_name': '{} Войти в группу по названию',
#             'my_groups': '{} Мои игровые группы',
#             'admin_groups': '{} Игровые группы, в которых я являюсь администратором',
#             'groups_languages': '{} Языки: {}',
#             'groups_help': '{} Справка',
#         },
#         'menu_texts': {
#             'join_game': 'Выберите способ присоединения к игре',
#             'popular_groups': 'Популярные игровые группы.',
#             'admin_groups': 'Список групп, в которых Вы являетесь администратором',
#             'my_groups': 'Список Ваших игровых групп',
#             'welcome_private': 'Добро пожаловать, <b>{}</b>!',
#             'found_groups': 'Результаты поиска по запросу <b>{}</b>.',
#         },
#         'info_texts': {
#             'group_info': "Группа <b>{}</b>\n\n"
#                           "{} Доступность группы: <b>{}</b>\n"
#                           "{} Дата начала игры: <b>{}</b>\n"
#                           "{} Рейтинг: <b>{}</b>\n"
#                           "{} Язык группы: <b>{} {}</b>\n"
#                           "{} Баланс группы: <b>{}</b>\n",
#             'opened_group': 'открытая группа',
#             'closed_group': 'закрытая группа',
#             'private_group': 'доступ по паролю',
#             '1_month': 'января',
#             '2_month': 'февраля',
#             '3_month': 'марта',
#             '4_month': 'апреля',
#             '5_month': 'мая',
#             '6_month': 'июня',
#             '7_month': 'июля',
#             '8_month': 'августа',
#             '9_month': 'сентября',
#             '10_month': 'октября',
#             '11_month': 'ноября',
#             '12_month': 'декабря',
#             'group_accessibility': '{} Общедоступная группа;\n'
#                                    '{} Закрытая группа;\n'
#                                    '{} Группа с паролем;\n'
#                                    '{} Группа, к которой у Вас есть доступ;\n'
#                                    '{} Группа, в которой Вы являетесь администратором;\n'
#                                    '{} Ваша группа',
#         },
#         'error_message_texts': {
#             'closed_group': 'Это закрытая группа. Вы не можете присоединиться к ней',
#         }
#     }
# ))
# asyncio.gather(*[edit_texts(
#     {
#         'menu_texts': {
#             'admin_groups': 'Популярные группы.'
#         }
#     }),
#     add_texts(
#         {
#             'button_texts': {
#                 'groups_help': '{} Справка'
#             },
#             'info_texts': {
#                 'group_accessibility': '{} Общедоступная группа;\n'
#                                        '{} Закрытая группа;\n'
#                                        '{} Группа с паролем;\n'
#                                        '{} Группа, к которой у Вас есть доступ;\n'
#                                        '{} Группа, в которой Вы являетесь администратором;\n'
#                                        '{} Ваша группа'
#             }
#         }
#     )
# ]
# )

# asyncio.run(add_texts(
#     {
#         'error_message_texts': {
#             'incorrect_password': 'Неверный пароль. Попробуйте ввести другой.',
#             'group_was_deleted': 'Группа была удалена или перестала быть игровой.'
#         },
#         'selection_texts': {
#             'group_access': 'Вы успешно получили доступ к группе <b>{}</b>. Нажмите кнопку, чтобы войти.',
#         },
#         'button_texts': {
#             'back_to_menu': 'Назад в меню',
#             'enter_group': '{} Войти в группу'
#         }
#     }
# ))

# asyncio.run(add_texts(
#     {
#         'button_texts': {
#             'yes': '{} Да',
#             'no': '{} Нет',
#             'langs_no': '{} Нет, выбрать другой язык',
#             'select_lang': '{} Выбрать язык',
#         },
#         'menu_texts': {
#             'welcome_group': 'Добро пожаловать'
#         },
#         'error_message_texts': {
#             'only_creator_can': 'Только создателю группы доступно это действие. Вы можете {} ему',
#             'only_admins_can': 'Только администраторам группы доступно это действие. Список администраторов:\n\n{}',
#         }
#     }
# ))


# asyncio.run(edit_texts({
#     'error_message_texts': {
#         'only_creator_can': 'Только создателю группы доступно это действие. Вы можете {} ему',
#         'only_admins_can': 'Только администраторам группы доступно это действие. Список администраторов:\n\n{}',
#     },
# }))

# asyncio.run(add_texts({
#     'error_message_texts': {
#         'permissions_denied_member': '{} К сожалению, вы не можете сделать это, поскольку не являетесь создателем/администратором группы',
#         'permissions_denied_privacy': '{} К сожалению, вы не можете сделать это из-за настроек группы'
#     },
#     'button_texts': {
#         'shop': '{} Магазин',
#         'ratings': '{} Рейтинги',
#         'my_achievements': '{} Мои достижения',
#         'my_settings': '{} Мои настройки',
#         'group_settings': '{} Настройки группы',
#         'start_game': '{} Начать игру',
#         'help': '{} Помощь',
#         'add_bot_to_group': '{} Добавить бота в группу',
#     },
#     'info_texts': {
#         'user_profile': ''
#     }
# }))

# asyncio.run(add_lang_names_translations())
