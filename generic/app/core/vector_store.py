"""
Vector Store module using ChromaDB for semantic service search.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

import chromadb
from sentence_transformers import SentenceTransformer

from config import FilePathConfig

logger = logging.getLogger(__name__)


class ServiceVectorStore:
    """ChromaDB-based vector store for semantic service search."""
    
    _instance: Optional['ServiceVectorStore'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if ServiceVectorStore._initialized:
            return
            
        self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self._services: Dict[str, Dict] = {}
        
        # Initialize ChromaDB with persistent storage
        persist_dir = Path(FilePathConfig.VECTOR_STORE_DIR)
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        
        self._collection = self._client.get_or_create_collection(
            name="services",
            metadata={"hnsw:space": "cosine"}
        )
        
        self._load_and_index_services()
        ServiceVectorStore._initialized = True
        logger.info("ServiceVectorStore initialized")
    
    def _load_and_index_services(self) -> None:
        """Load services from JSON and index them into ChromaDB."""
        try:
            with open(FilePathConfig.SERVICE_DATA_FILE, 'r') as f:
                services = json.load(f)
            
            # Check if already indexed
            if self._collection.count() == len(services):
                logger.info(f"Services already indexed ({len(services)} services)")
                # Load services into memory for quick lookup
                for service in services:
                    self._services[service['service_id']] = service
                return
            
            # Clear and re-index
            self._client.delete_collection("services")
            self._collection = self._client.create_collection(
                name="services",
                metadata={"hnsw:space": "cosine"}
            )
            
            documents = []
            metadatas = []
            ids = []
            
            for service in services:
                self._services[service['service_id']] = service
                
                # Create rich text representation for embedding
                doc = self._build_service_document(service)
                documents.append(doc)
                
                # Extract cities for metadata
                cities = ','.join([c['city_name'].lower() for c in service['availability']])
                
                metadatas.append({
                    "service_id": service['service_id'],
                    "name": service['name'],
                    "category": service['category']['name'],
                    "price": float(service['pricing']['base_price']),
                    "cities": cities  # Add cities for filtering
                })
                ids.append(service['service_id'])
            
            # Generate embeddings and add to collection
            embeddings = self._embedding_model.encode(documents).tolist()
            
            self._collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Indexed {len(services)} services into vector store")
            
        except Exception as e:
            logger.error(f"Failed to load/index services: {e}")
            raise
    
    def _build_service_document(self, service: Dict) -> str:
        """Build a rich text document for semantic embedding."""
        parts = [
            f"Service: {service['name']}",
            f"Category: {service['category']['name']}",
            f"Subcategory: {service['subcategory']['name']}",
            f"Description: {service['description']}",
        ]
        
        # Add keywords and synonyms for better matching
        keywords = self._generate_keywords(service)
        if keywords:
            parts.append(f"Keywords: {', '.join(keywords)}")
        
        return " | ".join(parts)
    
    def _generate_keywords(self, service: Dict) -> List[str]:
        """Generate additional keywords for better search matching."""
        keywords = []
        
        category = service['category']['name'].lower()
        name = service['name'].lower()
        
        # Add common synonyms
        synonym_map = {
            'plumbing': ['plumber', 'pipe', 'water', 'leak', 'faucet', 'tap', 'drain', 'toilet', 'bathroom', 'leakage'],
            'cleaning': ['clean', 'wash', 'scrub', 'maid', 'housekeeping', 'sanitization', 'deep clean', 'steam'],
            'appliances': ['repair', 'fix', 'broken', 'not working', 'service', 'ac', 'fridge', 'washing machine', 'microwave', 'geyser', 'chimney', 'inverter', 'stove'],
            'electrician': ['electrical', 'electric', 'wire', 'wiring', 'light', 'fan', 'switch', 'mcb', 'circuit'],
            'painting': ['paint', 'wall', 'color', 'interior', 'exterior', 'waterproof', 'damp'],
            'pest control': ['pest', 'cockroach', 'ant', 'insect', 'bug', 'termite', 'bed bug', 'mosquito'],
            'salon': ['haircut', 'hair', 'beauty', 'grooming', 'styling', 'makeup', 'facial', 'manicure', 'pedicure'],
            'massage': ['spa', 'relaxation', 'therapy', 'body', 'stress relief'],
            'car care': ['car', 'vehicle', 'auto', 'automobile', 'wash', 'interior', 'foam'],
            'fitness': ['yoga', 'zumba', 'trainer', 'workout', 'exercise', 'gym'],
            'pet care': ['pet', 'dog', 'cat', 'grooming', 'walking', 'animal'],
            'healthcare': ['physiotherapy', 'therapy', 'medical', 'doctor', 'physio'],
            'tech support': ['laptop', 'mobile', 'phone', 'screen', 'computer', 'repair'],
            'home improvement': ['safety net', 'curtain', 'mosquito net', 'balcony', 'installation'],
            'security': ['cctv', 'camera', 'home theater', 'wiring', 'surveillance'],
            'gardening': ['garden', 'plant', 'pruning', 'lawn', 'maintenance'],
            'carpentry': ['carpenter', 'furniture', 'door', 'lock', 'kitchen', 'trolley', 'assembly', 'hinge']
        }
        
        for key, synonyms in synonym_map.items():
            if key in category or key in name:
                keywords.extend(synonyms)
        
        return list(set(keywords))
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Semantic search for services matching the query.
        
        Args:
            query: Natural language search query
            top_k: Maximum number of results to return
            
        Returns:
            List of matching services with similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self._embedding_model.encode([query]).tolist()
            
            # Search in ChromaDB
            results = self._collection.query(
                query_embeddings=query_embedding,
                n_results=min(top_k, self._collection.count()),
                include=["metadatas", "distances"]
            )
            
            matched_services = []
            
            if results['ids'] and results['ids'][0]:
                for i, service_id in enumerate(results['ids'][0]):
                    service = self._services.get(service_id)
                    if service:
                        # Convert distance to similarity (cosine distance to similarity)
                        distance = results['distances'][0][i] if results['distances'] else 0
                        similarity = 1 - distance
                        
                        matched_services.append({
                            'service': service,
                            'similarity': similarity
                        })
            
            logger.info(f"Search '{query}' found {len(matched_services)} results")
            return matched_services
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_service_by_id(self, service_id: str) -> Optional[Dict]:
        """Get a service by its ID."""
        return self._services.get(service_id)
    
    def get_all_services(self) -> List[Dict]:
        """Get all services."""
        return list(self._services.values())


# Global instance
_vector_store: Optional[ServiceVectorStore] = None


def get_vector_store() -> ServiceVectorStore:
    """Get the singleton vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = ServiceVectorStore()
    return _vector_store
