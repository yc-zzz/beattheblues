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
  methods: ['GET', 'POST','DELETE'],
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

app.post('/playlist', async (req, res) => {
  const { username, song } = req.body;

  if (!username || !song) {
    return res.status(400).json({ message: 'Missing data' });
  }

  try {
    await db.query(
      'INSERT INTO playlist (username, song) VALUES ($1, $2)',
      [username, song]
    );
    res.json({ message: 'Song saved to playlist!' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ message: 'Error saving song' });
  }
});

app.get('/playlist', async (req, res) => {
  const username = req.query.user;

  if (!username) {
    return res.status(400).json({ message: 'Username required' });
  }

  try {
    const result = await db.query(
      'SELECT id, song, added_at FROM playlist WHERE username = $1 ORDER BY added_at DESC',
      [username]
    );
    res.json(result.rows);
  } catch (err) {
    console.error('Failed to fetch playlist:', err);
    res.status(500).json({ message: 'Failed to fetch playlist' });
  }
});

app.delete('/playlist/:id', async (req, res) => {
  const { id } = req.params;

  try {
    await db.query('DELETE FROM playlist WHERE id = $1', [id]);
    res.json({ message: 'Song removed' });
  } catch (err) {
    console.error('Failed to delete song:', err);
    res.status(500).json({ message: 'Failed to delete song' });
  }
});


