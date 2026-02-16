# OmniAgent
**Universal Conversational AI for Every Domain**

A production-grade, domain-agnostic conversational AI agent framework built on LangGraph and DOST protocol. Switch between domains (food delivery, home services, e-commerce) with zero code changes.

---

## 🌟 Features

- **🔄 Domain-Agnostic Architecture** - One framework, infinite domains
- **🎯 DOST Protocol Compliant** - Full v00.01.01 specification support
- **🎨 Interactive Playground** - Beautiful CLI with dostEvent visualization
- **📦 Type-Safe** - 85% type coverage with Pydantic models
- **⚡ Production-Ready** - Error handling, logging, session management
- **🔧 Config-Driven** - Switch domains via YAML configs

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
cd omni-agent

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Add your OPENAI_API_KEY to .env


# Run Playground
# Food Delivery (Swiggy)
python playground.py --config configs/swiggy.yaml -v

# Home Services (Urban Company)
python playground.py --config configs/urban_company.yaml -v

# Fashion Shopping (Myntra)
python playground.py --config configs/myntra.yaml

# Run All Domain Tests
python test_all_domains.py
