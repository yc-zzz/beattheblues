const express = require('express');
const bcrypt = require('bcrypt');
const cors = require('cors');
const db = require('./db');
const app = express();
const PORT = process.env.PORT || 5000;

const allowedOrigins = [
  'http://localhost:3000',
  'https://beattheblues.vercel.app'
];

app.use(cors({
  origin: function (origin, callback) {
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  methods: ['GET', 'POST'],
  credentials: true
}));

app.use(express.json());

app.post('/register', async (req, res) => {
  const { username, email, password } = req.body;

  if (!username || !email || !password) {
    return res.status(400).json({ success: false, message: 'All fields are required.' });
  }

  try {
    const result = await db.query(
      'SELECT * FROM users WHERE username = $1 OR email = $2',
      [username, email]
    );
    const existing = result.rows;

    if (existing.length > 0) {
      return res.status(400).json({ success: false, message: 'Username or email already taken.' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    await db.query(
      'INSERT INTO users (username, email, password) VALUES ($1, $2, $3)',
      [username, email, hashedPassword]
    );

    res.json({ success: true, message: 'User registered successfully.' });
  } catch (error) {
    console.error('Registration error:', error);
    res.status(500).json({ success: false, message: 'Server error during registration.' });
  }
});

app.post('/login', async (req, res) => {
  const { username, password } = req.body;

  try {
    const result = await db.query(
      'SELECT * FROM users WHERE username = $1',
      [username]
    );
    const user = result.rows[0];

    if (!user) {
      return res.status(401).json({ success: false, message: 'User not found.' });
    }

    const isMatch = await bcrypt.compare(password, user.password);

    if (!isMatch) {
      return res.status(401).json({ success: false, message: 'Invalid password.' });
    }

    res.status(200).json({ success: true, username: user.username });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ success: false, message: 'Server error during login.' });
  }
});

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
