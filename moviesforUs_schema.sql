-- MoviesForUs Database Schema
-- Version 1.0
-- Compatible with PostgreSQL

-- Drop existing tables if they exist (in reverse order of creation to handle dependencies)
DROP TABLE IF EXISTS movie_ratings;
DROP TABLE IF EXISTS movie_genres;
DROP TABLE IF EXISTS movie_languages;
DROP TABLE IF EXISTS movies;
DROP TABLE IF EXISTS users;
DROP TYPE IF EXISTS movie_status;
DROP TYPE IF EXISTS user_role;

-- Create user roles enum
CREATE TYPE user_role AS ENUM ('user', 'admin', 'moderator');

-- Create movie status enum
CREATE TYPE movie_status AS ENUM ('pending', 'approved', 'rejected');

-- Users Table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role user_role DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    profile_picture VARCHAR(255),
    date_joined TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Movies Table
CREATE TABLE movies (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    filename VARCHAR(255) NOT NULL,
    thumbnail VARCHAR(255),
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    file_size BIGINT,
    duration_seconds INTEGER,
    status movie_status DEFAULT 'pending',
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    views_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0
);

-- Movie Languages Table
CREATE TABLE movie_languages (
    id SERIAL PRIMARY KEY,
    movie_id INTEGER REFERENCES movies(id) ON DELETE CASCADE,
    language VARCHAR(50) NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE
);

-- Movie Genres Table
CREATE TABLE movie_genres (
    id SERIAL PRIMARY KEY,
    movie_id INTEGER REFERENCES movies(id) ON DELETE CASCADE,
    genre VARCHAR(50) NOT NULL
);

-- Movie Ratings Table
CREATE TABLE movie_ratings (
    id SERIAL PRIMARY KEY,
    movie_id INTEGER REFERENCES movies(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    rating_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(movie_id, user_id)
);

-- Indexes for performance
CREATE INDEX idx_movies_user_id ON movies(user_id);
CREATE INDEX idx_movies_status ON movies(status);
CREATE INDEX idx_movie_languages_movie_id ON movie_languages(movie_id);
CREATE INDEX idx_movie_genres_movie_id ON movie_genres(movie_id);
CREATE INDEX idx_movie_ratings_movie_id ON movie_ratings(movie_id);
CREATE INDEX idx_movie_ratings_user_id ON movie_ratings(user_id);

-- Sample Data Insertion

-- Insert sample users
INSERT INTO users (username, email, password_hash, role) VALUES
('admin', 'admin@moviesforus.com', '$2b$12$9ZXx/7rWm6QuIjP6LaL9aOQs0nRRbrT4XxPOBTPMNVRrQqEkwOKRa', 'admin'),
('moviefan', 'user1@example.com', '$2b$12$9ZXx/7rWm6QuIjP6LaL9aOQs0nRRbrT4XxPOBTPMNVRrQqEkwOKRa', 'user'),
('cinephile', 'user2@example.com', '$2b$12$9ZXx/7rWm6QuIjP6LaL9aOQs0nRRbrT4XxPOBTPMNVRrQqEkwOKRa', 'user');

-- Insert sample movies
INSERT INTO movies (title, description, filename, thumbnail, status, user_id, views_count) VALUES
('Inception', 'A mind-bending sci-fi thriller', 'inception.mp4', 'inception_thumb.jpg', 'approved', 1, 1000),
('The Matrix', 'Reality is not what it seems', 'matrix.mp4', 'matrix_thumb.jpg', 'approved', 2, 1500),
('Interstellar', 'Space exploration and time dilation', 'interstellar.mp4', 'interstellar_thumb.jpg', 'pending', 3, 500);

-- Insert movie languages
INSERT INTO movie_languages (movie_id, language, is_primary) VALUES
(1, 'English', true),
(2, 'English', true),
(3, 'English', true);

-- Insert movie genres
INSERT INTO movie_genres (movie_id, genre) VALUES
(1, 'Science Fiction'),
(1, 'Action'),
(2, 'Science Fiction'),
(2, 'Action'),
(3, 'Science Fiction'),
(3, 'Drama');

-- Insert movie ratings
INSERT INTO movie_ratings (movie_id, user_id, rating, review_text) VALUES
(1, 2, 5, 'Mind-blowing movie!'),
(2, 3, 4, 'A classic sci-fi film'),
(3, 1, 5, 'Christopher Nolan at his best');

-- Comments
COMMENT ON TABLE users IS 'Stores user account information';
COMMENT ON TABLE movies IS 'Contains details about uploaded movies';
COMMENT ON TABLE movie_languages IS 'Tracks languages for each movie';
COMMENT ON TABLE movie_genres IS 'Categorizes movies by genre';
COMMENT ON TABLE movie_ratings IS 'Stores user ratings and reviews for movies';

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
