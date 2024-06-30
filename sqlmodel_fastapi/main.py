from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, create_engine, select


class HeroBase(SQLModel):
    name: str = Field(index=True)
    secret_name: str
    age: int | None = Field(default=None, index=True)


class Hero(HeroBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str = Field()


class HeroCreate(HeroBase):
    password: str


class HeroPublic(HeroBase):
    id: int


class HeroUpdate(SQLModel):
    name: str | None = None
    secret_name: str | None = None
    age: int | None = None
    password: str | None = None


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def hash_password(password: str) -> str:
    # Use algo como passlib aqui
    return f"not really hashed {password} hehehe"


app = FastAPI()


@app.on_event("startup")
async def on_startup():
    create_db_and_tables()


@app.post("/heroes/", response_model=HeroPublic)
def create_hero(hero: HeroCreate):
    hashed_password = hash_password(hero.password)
    with Session(engine) as session:
        extra_data = {"hashed_password": hashed_password}
        # o parâmetro upadate está recebendo um dicionário extra que será
        # incluído e irá atualizar o db_hero que também é um dicionário
        db_hero = Hero.model_validate(hero, update=extra_data)
        # breakpoint()
        session.add(db_hero)
        session.commit()
        session.refresh(db_hero)
        return db_hero


@app.get("/heroes/", response_model=list[HeroPublic])
# offsete indica que o retorno começa apartir do registro 0,
# limit limita o retorno padrão em 100 registros
# le indica qual o numero máximo de retornos limit pode receber
def read_heroes(offset: int = 0, limit: int = Query(default=100, le=100)):
    with Session(engine) as session:
        heroes = session.exec(select(Hero).offset(offset).limit(limit)).all()
        return heroes


@app.get("/heroes/{hero_id}", response_model=HeroPublic)
def read_hero(hero_id: int):
    with Session(engine) as session:
        hero = session.get(Hero, hero_id)
        if not hero:
            raise HTTPException(status_code=404, detail="Hero not found")
        return hero


@app.patch("/heroes/{hero_id}", response_model=HeroPublic)
def update_hero(hero_id: int, hero: HeroUpdate):
    with Session(engine) as session:
        db_hero = session.get(Hero, hero_id)

        if not db_hero:
            raise HTTPException(status_code=404, detail="Hero not found")

        # mode_dump transforma os dados enviados pelo cliente observando
        # o schema HeroUpdate. Já o parâmetro exclude_unset diz ao Pydantic
        # para não incluir os valores que não foram enviados pelo cliente
        hero_data = hero.model_dump(exclude_unset=True)

        extra_data = {}
        if "password" in hero_data:
            password = hero_data["password"]
            hashed_password = hash_password(password)
            extra_data["hashed_password"] = hashed_password
        # Para cada um dos campos no objeto do modelo original db_hero,
        # sqlmodel_update verifica se o campo está disponível no argumento
        # hero_data e então o atualiza com o valor fornecido
        # o parâmetro update aqui tem a mesma função do método create_hero
        db_hero.sqlmodel_update(hero_data, update=extra_data)
        session.add(db_hero)
        session.commit()
        session.refresh(db_hero)
        return db_hero
