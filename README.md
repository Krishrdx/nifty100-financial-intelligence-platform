# NIFTY 100 Financial Intelligence Platform

The **NIFTY 100 Financial Intelligence Platform** is a comprehensive data analytics application designed to collect, process, analyze, and visualize financial information for companies listed in the NIFTY 100 index.

The platform follows an end-to-end data engineering workflow, beginning with data ingestion from structured financial datasets, followed by transformation and storage in a relational SQLite database. It provides analytical insights through financial ratio calculations, interactive dashboards, REST APIs, and automated reporting.

## Key Features

* End-to-End ETL (Extract, Transform, Load) Pipeline
* SQLite Database for Structured Financial Storage
* Financial Ratio Analysis (Liquidity, Profitability, Solvency, Efficiency)
* FastAPI-based REST API for Data Access
* Interactive Streamlit Dashboard
* Dynamic Charts and Visualizations
* Automated Report Generation
* Unit Testing using PyTest
* Modular and Production-Oriented Project Structure

## Technology Stack

* Python
* Pandas
* NumPy
* SQLite
* FastAPI
* Streamlit
* Plotly
* Matplotlib
* PyTest
* OpenPyXL

## Project Architecture


Raw Financial Data
        │
        ▼
ETL Pipeline
        │
        ▼
SQLite Database
        │
 ┌──────┴────────┐
 │               │
 ▼               ▼
Analytics     FastAPI
 │               │
 └──────┬────────┘
        ▼
 Streamlit Dashboard
        │
        ▼
 Reports & Financial Insights

The project demonstrates best practices in data engineering, backend development, financial analytics, database management, API development, and dashboard visualization, making it a complete financial intelligence solution for analyzing NIFTY 100 companies.
