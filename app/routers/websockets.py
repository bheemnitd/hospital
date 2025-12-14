from fastapi import WebSocket, WebSocketDisconnect, Depends, APIRouter
from sqlalchemy.orm import Session
from typing import Dict, List
import json
import asyncio
from .. import models, database


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, batch_id: str):
        await websocket.accept()
        if batch_id not in self.active_connections:
            self.active_connections[batch_id] = []
        self.active_connections[batch_id].append(websocket)

    def disconnect(self, websocket: WebSocket, batch_id: str):
        if batch_id in self.active_connections:
            self.active_connections[batch_id].remove(websocket)
            if not self.active_connections[batch_id]:
                del self.active_connections[batch_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast_to_batch(self, batch_id: str, message: dict):
        if batch_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[batch_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            
            for conn in disconnected:
                self.disconnect(conn, batch_id)

    async def get_progress_update(self, batch_id: str, db: Session) -> dict:
        print(f"WebSocket: Looking for batch_id: {batch_id}")
        
        bulk_op = db.query(models.BulkOperation).filter(
            models.BulkOperation.batch_id == batch_id
        ).first()
        
        if not bulk_op:
            print(f"WebSocket: Bulk operation not found for batch_id: {batch_id}")
            all_ops = db.query(models.BulkOperation).all()
            print(f"WebSocket: Available bulk operations: {[op.batch_id for op in all_ops]}")
            return {"error": "Batch not found"}
        
        print(f"WebSocket: Found bulk operation: {bulk_op.status}")
        
        progress_percentage = 0
        if bulk_op.total_hospitals > 0:
            progress_percentage = (bulk_op.processed_hospitals / bulk_op.total_hospitals) * 100
        
        return {
            "batch_id": batch_id,
            "status": bulk_op.status,
            "progress_percentage": round(progress_percentage, 2),
            "total_hospitals": bulk_op.total_hospitals,
            "processed_hospitals": bulk_op.processed_hospitals,
            "failed_hospitals": bulk_op.failed_hospitals,
            "processing_time_seconds": bulk_op.processing_time_seconds,
            "batch_activated": bulk_op.batch_activated,
            "error_message": bulk_op.error_message
        }


manager = ConnectionManager()

router = APIRouter()

@router.websocket("/ws/bulk/{batch_id}")
async def websocket_endpoint(websocket: WebSocket, batch_id: str):
    print(f"WebSocket: Connection attempt for batch_id: {batch_id}")
    await manager.connect(websocket, batch_id)
    print(f"WebSocket: Connected for batch_id: {batch_id}")
    
    try:
        db = next(database.get_db())
        print(f"WebSocket: Got database session")
        
        monitor_task = asyncio.create_task(progress_monitor(batch_id, db))
        print(f"WebSocket: Started progress monitoring")
        
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                print(f"WebSocket: Client disconnected for batch_id: {batch_id}")
                break
    except WebSocketDisconnect:
        print(f"WebSocket: WebSocket disconnected for batch_id: {batch_id}")
        pass
    finally:
        manager.disconnect(websocket, batch_id)
        print(f"WebSocket: Disconnected for batch_id: {batch_id}")
        if 'monitor_task' in locals():
            monitor_task.cancel()


async def progress_monitor(batch_id: str, db: Session):
    while True:
        try:
            progress_update = await manager.get_progress_update(batch_id, db)
            await manager.broadcast_to_batch(batch_id, progress_update)
            
            if progress_update.get("status") in ["completed", "failed"]:
                break
                
            await asyncio.sleep(1)
        except Exception as e:
            await manager.broadcast_to_batch(batch_id, {
                "error": f"Progress monitoring error: {str(e)}"
            })
            break
