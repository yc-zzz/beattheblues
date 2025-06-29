import express from 'express';
import bcrypt from 'bcrypt';
import db from '../db.js';
const router = express.Router();
//fyi 400 is bad request, 401 is unauthorised, 500 is server error
//register route
router.post('/register', async (req, res) => {
  const{username, email, password} = req.body;
  if (!username||!email||!password){ //check for any empty fields
    return res.status(400).json({success: false, message: 'Please fill up all fields'});
  }

  try {
    const result = await db.query(
      'SELECT * FROM users WHERE username = $1 OR email = $2', //checking for repeated username and email in db
      [username, email]
    );
    const existing = result.rows;
    
    if (existing.length > 0) { //if existing.length not zero, ie there is a username or email taken
      return res.status(400).json({success: false, message: 'Username or email taken.'});
    }
    const hashedPassword = await bcrypt.hash(password, 10); //10 rounds is standard apparently, can increase rounds for stronger hash but no point for us 
    await db.query(
      'INSERT INTO users (username, email, password) VALUES ($1, $2, $3)',//inserts the new user info into our db
      [username, email, hashedPassword]
    );
    res.json({success: true, message: 'User registered successfully.'});
  } 
  catch (err) {
    console.error(err);
    res.status(500).json({success: false, message: 'Server error during registration.'});
  }
});

//login route
router.post('/login', async (req, res) => {
  const {username, password} = req.body;

  try {
    const result = await db.query( 
      'SELECT * FROM users WHERE username = $1', //ie scanning usernames in db for match
      [username]
    );
    const user = result.rows[0];
    if (!user) {//no matching user
      return res.status(401).json({success: false, message: 'User not found.'});
    }

    const matched = await bcrypt.compare(password, user.password);//matching hashed password

    if (!matched) {
      return res.status(401).json({success: false, message: 'Invalid password.'});
    }

    res.status(200).json({success: true, username: user.username});
  } 
  
  catch (err) {
    console.error(err);
    res.status(500).json({success: false, message: 'Server error during login.'});
  }
});

export default router;
