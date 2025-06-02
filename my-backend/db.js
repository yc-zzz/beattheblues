const mysql = require('mysql2/promise');
require('dotenv').config();

const db = mysql.createPool({
    host: 'sql12.freesqldatabase.com',
    user: 'sql12782559',
    password: 'gdBipnhEqf',
    database: 'sql12782559',
    port: 3306,
});

module.exports = db;