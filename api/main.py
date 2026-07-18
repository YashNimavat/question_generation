from fastapi import FastAPI

from api.routers import documents, evaluations, experiments, questions, reviews

app = FastAPI(title="Question Intelligence API")

app.include_router(questions.router)
app.include_router(documents.router)
app.include_router(evaluations.router)
app.include_router(reviews.router)
app.include_router(experiments.router)
