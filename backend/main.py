import itertools
import json
import os
from datetime import datetime, timedelta

import requests
import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text, create_engine, delete, insert, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

Base = declarative_base()


user_news_association_table = Table(
    "user_news_upvotes",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column(
        "news_articles_id", Integer, ForeignKey("news_articles.id"), primary_key=True
    ),
)

# from pydantic import BaseModel


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    upvoted_news = relationship(
        "NewsArticle",
        secondary=user_news_association_table,
        back_populates="upvoted_by_users",
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    time = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    upvoted_by_users = relationship(
        "User", secondary=user_news_association_table, back_populates="upvoted_news"
    )


engine = create_engine("sqlite:///news_database.db", echo=True)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

sentry_sdk.init(
    dsn="https://4001ffe917ccb261aa0e0c34026dc343@o4505702629834752.ingest.us.sentry.io/4507694792704000",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

app = FastAPI()
task_scheduler = BackgroundScheduler()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app.add_middleware(
    CORSMiddleware,  # noqa
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from openai import OpenAI


# def generate_summary(content):
#     m = [
#         {
#             "role": "system",
#             "content": "你是一個新聞摘要生成機器人，請統整新聞中提及的影響及主要原因 (影響、原因各50個字，請以json格式回答 {'影響': '...', '原因': '...'})",
#         },
#         {"role": "user", "content": f"{content}"},
#     ]
#
#     completion = OpenAI(api_key="xxx").chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=m,
#     )
#     return completion.choices[0].message.content

#
# def extract_search_keywords(content):
#     m = [
#         {
#             "role": "system",
#             "content": "你是一個關鍵字提取機器人，用戶將會輸入一段文字，表示其希望看見的新聞內容，請提取出用戶希望看見的關鍵字，請截取最重要的關鍵字即可，避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字，若有多個關鍵字，請以空格分隔)",
#         },
#         {"role": "user", "content": f"{content}"},
#     ]
#
#     completion = OpenAI(api_key="xxx").chat.completions.create(
#         model="gpt-3.5-turbo",
#         messages=m,
#     )
#     return completion.choices[0].message.content


from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session


def format_content(content_list: list) -> str:
    return " ".join(content_list)

def add_new_to_db(news_data: dict, session: Session) -> None:
    try:
        new_article = NewsArticle(
            url=news_data["url"],
            title=news_data["title"],
            time=news_data["time"],
            content=format_content(news_data["content"]),
            summary=news_data["summary"],
            reason=news_data["reason"],
        )
        session.add(new_article)
        session.commit()
    except Exception as e:
        logging.error(f"Error adding news to database: {e}")

def fetch_news_page(search_term: str, page: int) -> list:
    params = {
        "page": page,
        "id": f"search:{quote(search_term)}",
        "channelId": 2,
        "type": "searchword",
    }
    response = requests.get("https://udn.com/api/more", params=params)
    return response.json().get("lists", [])

def get_new_info(search_term: str, is_initial: bool = False) -> list:
    all_news_data = []

    if is_initial:
        news_pages = [fetch_news_page(search_term, page) for page in range(1, 10)]
        for page_data in news_pages:
            all_news_data.extend(page_data)
    else:
        all_news_data = fetch_news_page(search_term, 1)

    return all_news_data

def evaluate_relevance(title: str) -> str:
    """使用 AI 模型評估新聞標題的相關性。"""
    messages = [
        {
            "role": "system",
            "content": "你是一個關聯度評估機器人，請評估新聞標題是否與「民生用品的價格變化」相關，並給予 'high'、'medium'、'low' 評價。",
        },
        {"role": "user", "content": title},
    ]
    ai = OpenAI(api_key="xxx").chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    return ai.choices[0].message.content

def fetch_detailed_news_content(url: str) -> dict:
    """抓取並解析新聞網頁的詳細內容。"""
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("h1", class_="article-content__title").text
    time = soup.find("time", class_="article-content__time").text
    content_section = soup.find("section", class_="article-content__editor")
    paragraphs = [p.text for p in content_section.find_all("p") if p.text.strip() != "" and "▪" not in p.text]
    return {"url": url, "title": title, "time": time, "content": paragraphs}

def generate_summary(content: str) -> dict:
    """使用 AI 模型生成新聞摘要。"""
    messages = [
        {
            "role": "system",
            "content": "你是一個新聞摘要生成機器人，請統整新聞中的影響及原因（各 50 字，JSON 格式）。",
        },
        {"role": "user", "content": content},
    ]
    completion = OpenAI(api_key="xxx").chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    return json.loads(completion.choices[0].message.content)

def fetch_and_store_news_data(is_initial=False):
    """獲取並存儲新聞數據。"""
    news_data = get_new_info("價格", is_initial=is_initial)
    for news in news_data:
        if evaluate_relevance(news["title"]) == "high":
            detailed_news = fetch_detailed_news_content(news["titleLink"])
            summary = generate_summary(" ".join(detailed_news["content"]))
            detailed_news.update({"summary": summary["影響"], "reason": summary["原因"]})
            add_new_to_db(detailed_news)


@app.on_event("startup")
def start_scheduler():
    with SessionLocal() as db:
        if db.query(NewsArticle).count() == 0:
            fetch_and_store_news_data()
    
    task_scheduler.add_job(fetch_and_store_news_data, "interval", minutes=100)
    task_scheduler.start()


@app.on_event("shutdown")
def shutdown_scheduler():
    task_scheduler.shutdown()


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


def get_session():
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()



def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(db_session, username, password):
    user = db_session.query(User).filter(User.username == username).first()
    if user is None or not verify_password(password, user.hashed_password):
        return False
    return user


def authenticate_user_token(
    token = Depends(oauth2_scheme),
    db = Depends(get_session)
):
    payload = jwt.decode(token, '1892dhianiandowqd0n', algorithms=["HS256"])
    return db.query(User).filter(User.username == payload.get("sub")).first()


SECRET_KEY = '1892dhianiandowqd0n'
ALGORITHM = "HS256"

def create_access_token(data, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta if expires_delta else datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@app.post("/api/v1/users/login")
async def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_session)
):
    """login"""
    user = authenticate_user(db, form_data.username, form_data.password)
    access_token = create_access_token(
        data={"sub": str(user.username)}, expires_delta=timedelta(minutes=30)
    )
    return {"access_token": access_token, "token_type": "bearer"}

class UserAuthSchema(BaseModel):
    username: str
    password: str
@app.post("/api/v1/users/register")
def register_user(user: UserAuthSchema, db: Session = Depends(get_session)):
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken.")
    
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/api/v1/users/me")
def read_users_me(user=Depends(authenticate_user_token)):
    return {"username": user.username}


_id_counter = itertools.count(start=1000000)


def get_article_upvote_details(article_id: int, uid: int, db: Session) -> tuple[int, bool]:
    upvote_count = (
        db.query(user_news_association_table)
        .filter_by(news_articles_id=article_id)
        .count()
    )
    
    user_voted = False
    if uid:
        user_voted = (
            db.query(user_news_association_table)
            .filter_by(news_articles_id=article_id, user_id=uid)
            .first()
            is not None
        )
        
    return upvote_count, user_voted


@app.get("/api/v1/news/news")
def read_news(db=Depends(get_session)):
    """
    read new

    :param db:
    :return:
    """
    news_articles = db_session.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
    articles_with_upvotes = []
    for article in news_articles:
        upvotes, is_upvoted = get_article_upvote_details(article.id, None, db_session)
        articles_with_upvotes.append(
            {**article.__dict__, "upvotes": upvotes, "is_upvoted": is_upvoted}
        )
    return articles_with_upvotes


@app.get("/api/v1/news/user_news")
def read_user_news(
        db_session=Depends(get_session),
        current_user=Depends(authenticate_user_token)
):
    news_articles = db_session.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
    articles_with_upvotes = []
    for article in news_articles:
        upvotes, is_upvoted = get_article_upvote_details(article.id, current_user.id, db_session)
        articles_with_upvotes.append(
            {
                **article.__dict__,
                "upvotes": upvotes,
                "is_upvoted": is_upvoted,
            }
        )
    return articles_with_upvotes

class PromptRequest(BaseModel):
    prompt: str

@app.post("/api/v1/news/search_news")
async def search_news(request: PromptRequest):
    prompt = request.prompt
    news_articles = []
    messages = [
        {
            "role": "system",
            "content": "你是一個關鍵字提取機器人，用戶將會輸入一段文字，表示其希望看見的新聞內容，請提取出用戶希望看見的關鍵字，請截取最重要的關鍵字即可，避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字，若有多個關鍵字，請以空格分隔)",
        },
        {"role": "user", "content": f"{prompt}"},
    ]

    ai_response = OpenAI(api_key="xxx").chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    keywords = ai_response.choices[0].message.content

    fetched_articles = get_new_info(keywords, is_initial=False)
    for article in fetched_articles:
        try:
            response = requests.get(article["titleLink"])
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.find("h1", class_="article-content__title").text
            time = soup.find("time", class_="article-content__time").text
            content_section = soup.find("section", class_="article-content__editor")

            paragraphs = [
                p.text
                for p in content_section.find_all("p")
                if p.text.strip() != "" and "▪" not in p.text
            ]
            detailed_news = {
                "url": article["titleLink"],
                "title": title,
                "time": time,
                "content": " ".join(paragraphs),
                "id": next(_id_counter),
            }
            news_articles.append(detailed_news)
        except Exception as e:
            print(e)
    return sorted(news_articles, key=lambda x: x["time"], reverse=True)

class NewsSumaryRequestSchema(BaseModel):
    content: str

@app.post("/api/v1/news/news_summary")
async def news_summary(
        payload: NewsSummaryRequestSchema, current_user=Depends(authenticate_user_token)
):
    summary_response = {}
    messages = [
        {
            "role": "system",
            "content": "你是一個新聞摘要生成機器人，請統整新聞中提及的影響及主要原因 (影響、原因各50個字，請以json格式回答 {'影響': '...', '原因': '...'})",
        },
        {"role": "user", "content": f"{payload.content}"},
    ]

    ai_response = OpenAI(api_key="xxx").chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )
    parsed_result = ai_response.choices[0].message.content
    if parsed_result:
        parsed_result = json.loads(parsed_result)
        summary_response["summary"] = parsed_result["影響"]
        summary_response["reason"] = parsed_result["原因"]
    return summary_response


@app.post("/api/v1/news/{id}/upvote")
def upvote_article(
        id,
        db=Depends(get_session),
        u=Depends(authenticate_user_token),
):
    message = toggle_upvote(id, u.id, db)
    return {"message": message}


def toggle_upvote(n_id, u_id, db):
    existing_upvote = db.execute(
        select(user_news_association_table).where(
            user_news_association_table.c.news_articles_id == n_id,
            user_news_association_table.c.user_id == u_id,
        )
    ).scalar()

    if existing_upvote:
        delete_stmt = delete(user_news_association_table).where(
            user_news_association_table.c.news_articles_id == n_id,
            user_news_association_table.c.user_id == u_id,
        )
        db.execute(delete_stmt)
        db.commit()
        return "Upvote removed"
    else:
        insert_stmt = insert(user_news_association_table).values(
            news_articles_id=n_id, user_id=u_id
        )
        db.execute(insert_stmt)
        db.commit()
        return "Article upvoted"


def news_exists(id2, db: Session):
    return db.query(NewsArticle).filter_by(id=id2).first() is not None


@app.get("/api/v1/prices/necessities-price")
def get_necessities_prices(
        category=Query(None), commodity=Query(None)
):
    return requests.get(
        "https://opendata.ey.gov.tw/api/ConsumerProtection/NecessitiesPrice",
        params={"CategoryName": category, "Name": commodity},
    ).json()
