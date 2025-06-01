const express = require('express');
const bcrypt = require('bcrypt');
const cors = require('cors');
const db = require('./db');
//const authRoutes = require('./routes/auth');
//require('dotenv').config()
//const bodyParser = require('body-parser')
const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
//app.use(bodyParser.json());
app.use(express.json())

//app.get('/', (req,res) => {res.send('Backend is running');});
//app.use('./api', authRoutes)

app.post('/register', async (req, res) => {
  const { username, email, password } = req.body;

  if (!username || !email || !password) {
    return res.status(400).json({ success: false, message: 'All fields are required.' });
  }

  try {
    const [existing] = await db.execute(
      'SELECT * FROM users WHERE username = ? OR email = ?',
      [username, email]
    );

    if (existing.length > 0) {
      return res.status(400).json({ success: false, message: 'Username or email already taken.' });
    }
    
    const hashedPassword = await bcrypt.hash(password, 10);

    await db.execute(
      'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
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
    const [results] = await db.execute('SELECT * FROM users WHERE username = ?', [username]);

    if (results.length === 0) {
      return res.status(401).json({ success: false, message: 'User not found.' });
    }

    const user = results[0];
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


app.listen(PORT, ()=>{
    console.log(`Server is running on http://localhost:${PORT}`);
});
