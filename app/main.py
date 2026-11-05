from fastapi import FastAPI, HTTPException, status
from app.models import ItemCreate, ItemUpdate, ItemOut

app = FastAPI(title="S5 API cible", version="1.0.0")

_INITIAL_DB = {1: {"id": 1, "name": "cahier", "price": 12.0}}
_db: dict[int, dict] = {}
_next_id = 2


def reset_db() -> None:
    """Réinitialise la base entre tests (utilisé par le runner)."""
    global _db, _next_id
    _db = {k: dict(v) for k, v in _INITIAL_DB.items()}
    _next_id = 2


reset_db()


@app.get("/items", response_model=list[ItemOut])
def list_items():
    return list(_db.values())


@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int):
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Item not found")
    return _db[item_id]


@app.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate):
    global _next_id
    new = {"id": _next_id, **item.model_dump()}
    _db[_next_id] = new
    _next_id += 1
    return new


@app.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, item: ItemUpdate):
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Item not found")
    updated = {"id": item_id, **item.model_dump()}
    _db[item_id] = updated
    return updated


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int):
    if item_id not in _db:
        raise HTTPException(status_code=404, detail="Item not found")
    del _db[item_id]
    return None