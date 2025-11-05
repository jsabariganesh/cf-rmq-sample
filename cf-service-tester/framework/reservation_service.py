"""
Ticket Reservation Service
Handles CRUD operations for ticket reservations with optional caching and notifications
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class Reservation:
    id: int
    customer_name: str
    event_name: str
    event_date: str
    seat_number: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reservation':
        return cls(**data)

class ReservationService:
    """Service for managing ticket reservations"""
    
    def __init__(self, service_manager):
        self.service_manager = service_manager
        self.db = service_manager.database
        self.mq = service_manager.message_queue
        self.cache = service_manager.cache
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database schema and sample data"""
        try:
            # Create reservations table
            if self.db.db_type == 'postgres':
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS reservations (
                    id SERIAL PRIMARY KEY,
                    customer_name VARCHAR(255) NOT NULL,
                    event_name VARCHAR(255) NOT NULL,
                    event_date DATE NOT NULL,
                    seat_number VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            elif self.db.db_type == 'mysql':
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS reservations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_name VARCHAR(255) NOT NULL,
                    event_name VARCHAR(255) NOT NULL,
                    event_date DATE NOT NULL,
                    seat_number VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """
            else:  # SQLite (in-memory)
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    seat_number TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            
            self.db.execute_query(create_table_sql)
            logger.info("Reservations table created/verified")
            
            # Load sample data if configured
            if self.service_manager.config.sample_data.get('load_on_startup', False):
                self._load_sample_data()
        
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise
    
    def _load_sample_data(self):
        """Load sample reservation data"""
        try:
            # Check if data already exists
            existing = self.db.execute_query("SELECT COUNT(*) as count FROM reservations")
            count = existing[0]['count'] if existing else 0
            
            if count > 0:
                logger.info("Sample data already exists, skipping load")
                return
            
            sample_reservations = self.service_manager.config.sample_data.get('reservations', [])
            
            for reservation_data in sample_reservations:
                # Remove id for auto-increment
                reservation_data = reservation_data.copy()
                if 'id' in reservation_data:
                    del reservation_data['id']
                
                # Add timestamps
                now = datetime.now().isoformat()
                reservation_data['created_at'] = now
                reservation_data['updated_at'] = now
                
                self._insert_reservation(reservation_data)
            
            logger.info(f"Loaded {len(sample_reservations)} sample reservations")
        
        except Exception as e:
            logger.error(f"Failed to load sample data: {str(e)}")
    
    def _insert_reservation(self, reservation_data: Dict[str, Any]) -> int:
        """Insert a new reservation into the database"""
        if self.db.db_type in ['postgres', 'mysql']:
            insert_sql = """
            INSERT INTO reservations (customer_name, event_name, event_date, seat_number, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
        else:  # SQLite
            insert_sql = """
            INSERT INTO reservations (customer_name, event_name, event_date, seat_number, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        
        params = (
            reservation_data['customer_name'],
            reservation_data['event_name'],
            reservation_data['event_date'],
            reservation_data['seat_number'],
            reservation_data['status'],
            reservation_data.get('created_at', datetime.now().isoformat()),
            reservation_data.get('updated_at', datetime.now().isoformat())
        )
        
        self.db.execute_query(insert_sql, params)
        
        # Get the inserted ID
        if self.db.db_type == 'postgres':
            result = self.db.execute_query("SELECT LASTVAL() as id")
        elif self.db.db_type == 'mysql':
            result = self.db.execute_query("SELECT LAST_INSERT_ID() as id")
        else:  # SQLite
            result = self.db.execute_query("SELECT last_insert_rowid() as id")
        
        return result[0]['id'] if result else None
    
    def get_all_reservations(self) -> List[Reservation]:
        """Get all reservations"""
        try:
            # Try cache first if enabled
            cache_key = "all_reservations"
            if self.cache and self.cache.is_connected:
                cached_data = self.cache.get(cache_key)
                if cached_data:
                    logger.info("Retrieved reservations from cache")
                    reservations_data = json.loads(cached_data)
                    return [Reservation.from_dict(data) for data in reservations_data]
            
            # Query database
            results = self.db.execute_query(
                "SELECT * FROM reservations ORDER BY created_at DESC"
            )
            
            reservations = [Reservation.from_dict(dict(row)) for row in results]
            
            # Cache the results if cache is enabled
            if self.cache and self.cache.is_connected:
                cache_data = json.dumps([r.to_dict() for r in reservations])
                self.cache.set(cache_key, cache_data, ttl=300)  # 5 minutes
            
            logger.info(f"Retrieved {len(reservations)} reservations")
            return reservations
        
        except Exception as e:
            logger.error(f"Failed to get reservations: {str(e)}")
            return []
    
    def get_reservation_by_id(self, reservation_id: int) -> Optional[Reservation]:
        """Get a specific reservation by ID"""
        try:
            # Try cache first
            cache_key = f"reservation_{reservation_id}"
            if self.cache and self.cache.is_connected:
                cached_data = self.cache.get(cache_key)
                if cached_data:
                    logger.info(f"Retrieved reservation {reservation_id} from cache")
                    return Reservation.from_dict(json.loads(cached_data))
            
            # Query database
            if self.db.db_type in ['postgres', 'mysql']:
                query = "SELECT * FROM reservations WHERE id = %s"
            else:  # SQLite
                query = "SELECT * FROM reservations WHERE id = ?"
            
            results = self.db.execute_query(query, (reservation_id,))
            
            if results:
                reservation = Reservation.from_dict(dict(results[0]))
                
                # Cache the result
                if self.cache and self.cache.is_connected:
                    self.cache.set(cache_key, json.dumps(reservation.to_dict()), ttl=600)
                
                return reservation
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to get reservation {reservation_id}: {str(e)}")
            return None
    
    def create_reservation(self, reservation_data: Dict[str, Any]) -> Optional[Reservation]:
        """Create a new reservation"""
        try:
            # Add timestamps
            now = datetime.now().isoformat()
            reservation_data['created_at'] = now
            reservation_data['updated_at'] = now
            reservation_data['status'] = reservation_data.get('status', 'pending')
            
            # Insert into database
            reservation_id = self._insert_reservation(reservation_data)
            
            if reservation_id:
                # Get the created reservation
                reservation = self.get_reservation_by_id(reservation_id)
                
                # Clear cache
                self._invalidate_cache()
                
                # Send notification if MQ is enabled
                if self.mq and self.mq.is_connected:
                    self._send_notification('reservation_created', reservation.to_dict())
                
                logger.info(f"Created reservation {reservation_id}")
                return reservation
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to create reservation: {str(e)}")
            return None
    
    def update_reservation(self, reservation_id: int, update_data: Dict[str, Any]) -> Optional[Reservation]:
        """Update an existing reservation"""
        try:
            # Add updated timestamp
            update_data['updated_at'] = datetime.now().isoformat()
            
            # Build update query
            set_clauses = []
            params = []
            
            for key, value in update_data.items():
                if key != 'id':  # Don't update ID
                    set_clauses.append(f"{key} = %s" if self.db.db_type in ['postgres', 'mysql'] else f"{key} = ?")
                    params.append(value)
            
            if not set_clauses:
                return self.get_reservation_by_id(reservation_id)
            
            params.append(reservation_id)
            
            if self.db.db_type in ['postgres', 'mysql']:
                update_sql = f"UPDATE reservations SET {', '.join(set_clauses)} WHERE id = %s"
            else:  # SQLite
                update_sql = f"UPDATE reservations SET {', '.join(set_clauses)} WHERE id = ?"
            
            self.db.execute_query(update_sql, tuple(params))
            
            # Clear cache
            self._invalidate_cache(reservation_id)
            
            # Get updated reservation
            reservation = self.get_reservation_by_id(reservation_id)
            
            # Send notification if MQ is enabled
            if self.mq and self.mq.is_connected and reservation:
                self._send_notification('reservation_updated', reservation.to_dict())
            
            logger.info(f"Updated reservation {reservation_id}")
            return reservation
        
        except Exception as e:
            logger.error(f"Failed to update reservation {reservation_id}: {str(e)}")
            return None
    
    def delete_reservation(self, reservation_id: int) -> bool:
        """Delete a reservation"""
        try:
            # Get reservation before deletion for notification
            reservation = self.get_reservation_by_id(reservation_id)
            
            # Delete from database
            if self.db.db_type in ['postgres', 'mysql']:
                delete_sql = "DELETE FROM reservations WHERE id = %s"
            else:  # SQLite
                delete_sql = "DELETE FROM reservations WHERE id = ?"
            
            self.db.execute_query(delete_sql, (reservation_id,))
            
            # Clear cache
            self._invalidate_cache(reservation_id)
            
            # Send notification if MQ is enabled
            if self.mq and self.mq.is_connected and reservation:
                self._send_notification('reservation_deleted', reservation.to_dict())
            
            logger.info(f"Deleted reservation {reservation_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to delete reservation {reservation_id}: {str(e)}")
            return False
    
    def _invalidate_cache(self, reservation_id: int = None):
        """Invalidate cache entries"""
        if not self.cache or not self.cache.is_connected:
            return
        
        try:
            # Always clear the all reservations cache
            self.cache.connection.delete("all_reservations")
            
            # Clear specific reservation cache if ID provided
            if reservation_id:
                self.cache.connection.delete(f"reservation_{reservation_id}")
        
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {str(e)}")
    
    def _send_notification(self, event_type: str, reservation_data: Dict[str, Any]):
        """Send notification via message queue"""
        try:
            message = {
                'event_type': event_type,
                'timestamp': datetime.now().isoformat(),
                'reservation': reservation_data
            }
            
            queue_name = 'reservation_notifications'
            success = self.mq.publish_message(queue_name, message)
            
            if success:
                logger.info(f"Sent {event_type} notification for reservation {reservation_data.get('id')}")
            else:
                logger.warning(f"Failed to send {event_type} notification")
        
        except Exception as e:
            logger.error(f"Notification sending failed: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get reservation statistics"""
        try:
            stats = {}
            
            # Total reservations
            total_result = self.db.execute_query("SELECT COUNT(*) as count FROM reservations")
            stats['total_reservations'] = total_result[0]['count'] if total_result else 0
            
            # Reservations by status
            status_result = self.db.execute_query(
                "SELECT status, COUNT(*) as count FROM reservations GROUP BY status"
            )
            stats['by_status'] = {row['status']: row['count'] for row in status_result}
            
            # Recent reservations (last 7 days)
            if self.db.db_type in ['postgres', 'mysql']:
                recent_query = "SELECT COUNT(*) as count FROM reservations WHERE created_at >= NOW() - INTERVAL '7 days'"
            else:  # SQLite
                recent_query = "SELECT COUNT(*) as count FROM reservations WHERE created_at >= datetime('now', '-7 days')"
            
            recent_result = self.db.execute_query(recent_query)
            stats['recent_reservations'] = recent_result[0]['count'] if recent_result else 0
            
            return stats
        
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            return {}
