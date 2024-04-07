CREATE DATABASE IF NOT EXISTS yavka_ml_service;

USE yavka_ml_service;

CREATE TABLE IF NOT EXISTS gpt_summarize (
    prompt String,
    request String,
    response String,
    timestamp DateTime DEFAULT now()('Etc/UTC')
) ENGINE = MergeTree
ORDER BY (timestamp);
