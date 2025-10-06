from sqlalchemy.orm import Session
from models.schemas import Ship, Port, Contractor, Pollutant

def init_data(db: Session):
    if db.query(Ship).count() == 0:
        ships = ["Андрей Фирсов", "ВТ-2701", "ВТ-2702", "Валентин Груздев", "Дмитрий Покровский",
                 "Павел Юдин", "Юлий Макаренков", "Яков Гунин", "Сергей Терсков", "Александр Шемагин",
                 "Андропов", "ВТ-2502", "Александр 2"]
        for name in ships:
            db.add(Ship(name=name))
    
    if db.query(Port).count() == 0:
        ports = ["Ростов-на-Дону", "Азов", "Волгоград", "Ейск",
                 "Самара", "Астрахань", "КЕК"]
        for name in ports:
            db.add(Port(name=name))
    
    if db.query(Contractor).count() == 0:
        contractors = ["Интертрейд", "Азовпортофлот", "Гермес",
                       "Шишов", "Палатин", "Эко Шиппинг",
                       "Кайт Шиппинг", "Дельта"]
        for name in contractors:
            db.add(Contractor(name=name))
    
    if db.query(Pollutant).count() == 0:
        pollutants = ["Питьевая вода", "Хозфекальные воды", "Шлам", "Бытовой мусор"]
        for name in pollutants:
            db.add(Pollutant(name=name))
    
    db.commit()