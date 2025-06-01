const mysql = require('mysql2/promise');
require('dotenv').config();

const db = mysql.createPool({
    host: 'localhost',
    user: 'root',
    password: 'insert_password',
    database: 'auth_system',
});

module.exports = db;