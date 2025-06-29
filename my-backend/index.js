import express from 'express';
import cors from 'cors';
import db from './db.js';
import auth from './routes/auth.js';
import playlist from './routes/playlist.js';

const app = express();
const PORT = process.env.PORT || 5000;


//don't think we're just gonna allow any address through right
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
  credentials: true //enable sending cookie, may use in the future for sessions
}));

app.use(express.json());

//login and registering are all here
app.use(auth);

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});

//for sending, fetching and deleting saved songs
app.use(playlist);

