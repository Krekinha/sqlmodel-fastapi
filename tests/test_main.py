import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from sqlmodel_fastapi.main import Hero, app, get_session


# As fixtures do pytest funcionam como ad dependências do FastApi injetando nos
# testes uma função que é executada antes do teste iniciar, podendo ser usada
# por todos os testes evitando a duplicação de código
@pytest.fixture(name="session")
def session_fixture():
    # Devido uma limitação de thread do sqlite usamos o parâmetro
    # "check_same_thread" para evitar erro de thread durante os testes.
    # o parâmetro poolclass=StaticPool permite usarmos o banco na memória
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Cria todas as tabelas no banco de dados de teste. As definições das
    # tabelas estão sendo feitas no main.py, porém como estamos importando algo
    # desse arquivo, o código dele é executado incluindo a definição dos
    # modelos de tabela, e isso os registrará automaticamente
    # em SQLModel.metadata
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
# A session aqui está sendo fornecida pela fixture session_fixture
def client_fixture(session: Session):
    # define uma sessão de teste que irá substituir a sessão em produção
    def get_session_test():
        return session

    # substitui a session em produção pela session de teste criada
    app.dependency_overrides[get_session] = get_session_test

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# O client aqui está sendo fornecida pela fixture client_fixture
def test_create_hero(client: TestClient):
    response = client.post(
        "/heroes/",
        json={
            "name": "Deadpond",
            "secret_name": "Dive Wilson",
            "password": "123",
        },
    )

    # desvincula do app a session de teste criada
    app.dependency_overrides.clear()

    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "Deadpond"
    assert data["secret_name"] == "Dive Wilson"
    assert data["age"] is None
    assert data["id"] is not None


def test_create_hero_incompleto(client: TestClient):
    # Sem o campo secret_name
    response = client.post("/heroes/", json={"name": "Deadpond"})

    assert response.status_code == 422


def test_create_hero_invalid(client: TestClient):
    # secret_name é um tipo inválido
    response = client.post(
        "/heroes/",
        json={
            "name": "Deadpond",
            "secret_name": {
                "message": "Do you wanna know my secret identity?"
            },
        },
    )

    assert response.status_code == 422


def test_read_heroes(session: Session, client: TestClient):
    client.post(
        "/heroes/",
        json={
            "name": "Deadpond",
            "secret_name": "Dive Wilson",
            "password": "123",
        },
    )
    client.post(
        "/heroes/",
        json={
            "name": "Rusty-Man",
            "secret_name": "Tomy Sharp",
            "age": 48,
            "password": "123",
        },
    )

    response = client.get("/heroes/")
    data = response.json()

    assert response.status_code == 200

    assert len(data) == 2
    assert data[0]["name"] == "Deadpond"
    assert data[0]["secret_name"] == "Dive Wilson"
    assert data[0]["age"] is None
    assert data[0]["id"] == 1
    assert data[1]["name"] == "Rusty-Man"
    assert data[1]["secret_name"] == "Tomy Sharp"
    assert data[1]["age"] == 48
    assert data[1]["id"] == 2


def test_read_hero(session: Session, client: TestClient):
    client.post(
        "/heroes/",
        json={
            "name": "Deadpond",
            "secret_name": "Dive Wilson",
            "password": "123",
        },
    )

    response = client.get(f"/heroes/{1}")
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "Deadpond"
    assert data["secret_name"] == "Dive Wilson"
    assert data["age"] is None
    assert data["id"] == 1


def test_update_hero(session: Session, client: TestClient):
    client.post(
        "/heroes/",
        json={
            "name": "Deadpond",
            "secret_name": "Dive Wilson",
            "password": "123",
        },
    )

    response = client.patch(f"/heroes/{1}", json={"name": "Deadpuddle"})
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "Deadpuddle"
    assert data["secret_name"] == "Dive Wilson"
    assert data["age"] is None
    assert data["id"] == 1


def test_delete_hero(session: Session, client: TestClient):
    client.post(
        "/heroes/",
        json={
            "name": "Deadpond",
            "secret_name": "Dive Wilson",
            "password": "123",
        },
    )

    response = client.delete(f"/heroes/{1}")

    hero_in_db = session.get(Hero, 1)

    assert response.status_code == 200

    assert hero_in_db is None
