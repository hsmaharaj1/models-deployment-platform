# PROJECT MEMORY NOTE 

## Owner

Himanshu Sekhar

## Context

I will be joining ServiceNow as a Machine Learning Engineer in November.

My goal before joining is NOT to build another generic ML project, chatbot, image classifier, or tutorial-style application.

I want to build a project that would genuinely impress senior MLEs and strengthen my resume for future opportunities.

The chosen flagship project is:

**ML Deployment Platform (Production-Grade MLOps System)**

---

# Why This Project Was Chosen

Current resume already contains:

- EventLink (full-stack recommendation platform)
- ML/DL projects
- GAN implementations
- Scientific ML exposure (FNO / Neural Operators)
- ServiceNow MLE offer

Gap identified:

I lack a strong demonstration of:

- Production ML systems
- Model serving
- Deployment infrastructure
- Monitoring
- Model lifecycle management
- MLOps architecture

This project is intended to fill that gap.

---

# High-Level Vision

Build a production-style platform where users can:

1. Upload trained ML models
2. Version models
3. Deploy inference endpoints
4. Monitor model performance
5. Track usage metrics
6. Trigger retraining workflows
7. Roll back to previous versions

The platform should feel like a simplified internal MLOps product.

Think:

"Mini SageMaker + MLflow + internal deployment platform"

---

# Resume Goal

Target resume bullet:

Designed and built a production-grade ML deployment platform supporting model versioning, asynchronous inference pipelines, automated deployment workflows, monitoring dashboards, and model lifecycle management.

Potential supporting bullets:

- Implemented Docker-based model serving architecture with isolated inference environments.
- Built asynchronous job processing using Redis-backed task queues.
- Developed model registry with version tracking and deployment rollback capabilities.
- Designed monitoring dashboard for latency, throughput, and deployment health metrics.

---

# Primary Learning Goals

This project is primarily intended to learn:

## Infrastructure

- Docker
- Containerization
- Image management
- Deployment workflows

## Backend

- FastAPI
- Async APIs
- Authentication
- Background jobs

## MLOps

- Model registry
- Model versioning
- Model serving
- Monitoring
- Retraining workflows

## System Design

- Service architecture
- Scalability concepts
- Production design tradeoffs

---

# Proposed Architecture

## Frontend  
|  
React  
|  
FastAPI Backend  
|

| | | |  
Registry Queue Monitoring Storage  
|  
Redis  
|  
Workers  
|  
Dockerized Inference Services

Core components:

1. Frontend
2. FastAPI Backend
3. Model Registry
4. Redis Queue Layer
5. Worker Layer
6. Monitoring Layer
7. Deployment Layer

---

# Phase Breakdown

## Phase 1 — Core Platform

Build:

- User authentication
- Project creation
- Model upload
- Metadata storage
- Model listing

Deliverable:  
Working model registry.

---

## Phase 2 — Deployment System

Build:

- Dockerized serving
- Endpoint generation
- Model activation/deactivation
- Version management

Deliverable:  
Users can deploy a model and call an inference API.

---

## Phase 3 — Async Processing

Build:

- Redis integration
- Background jobs
- Queue processing

Deliverable:  
Inference jobs handled asynchronously.

---

## Phase 4 — Monitoring

Build:

- Request tracking
- Latency tracking
- Error tracking
- Deployment health dashboard

Deliverable:  
Operational visibility.

---

## Phase 5 — Advanced Features

Optional:

- Auto-retraining triggers
- A/B deployments
- Canary deployments
- Resource monitoring
- Usage analytics

---

# Preferred Tech Stack

Backend:

- Python
- FastAPI

Frontend:

- React
- TypeScript

Database:

- PostgreSQL

Caching / Queue:

- Redis

Containers:

- Docker

Orchestration (later):

- Kubernetes

Monitoring:

- Prometheus
- Grafana

Authentication:

- JWT

Deployment:

- AWS or local Docker environment

---

# Success Criteria

By November:

The project should demonstrate:

- Production engineering ability
- MLOps understanding
- Deployment knowledge
- System design capability

More important than model accuracy:

- Architecture
- Scalability
- Reliability
- Developer experience

---

# Future Expansion

Potential second project after this:

Enterprise LLM Evaluation Platform

Features:

- Hallucination detection
- Prompt evaluation
- Retrieval benchmarking
- Cost tracking
- Latency analysis

This would complement the ML Deployment Platform and create a strong MLE portfolio.

---

# Guiding Principle

Do not optimize for:

- Number of features
- Fancy UI
- Buzzwords

Optimize for:

"Could a senior MLE look at this architecture and say:  
'This person understands how ML systems are built and shipped.'"