const router = express.Router();
import db from '../db.js';

//for sending saved songs to db
router.post('/playlist', async (req, res) => {
  const {username, song} = req.body;

  try {
    await db.query(
      'INSERT INTO playlist (username, song) VALUES ($1, $2)',
      [username, song]
    );
    res.json({message: 'Song saved to playlist!'});
  } 
  catch (err) {
    console.error(err);
    res.status(500).json({message: 'Error saving song'});
  }
});
//getting saved songs for the playlist page in frontend
router.get('/playlist', async (req, res) => {
  const username = req.query.user;

  try {
    const result = await db.query(
      'SELECT id, song, added_at FROM playlist WHERE username = $1 ORDER BY added_at DESC',
      [username]
    );
    res.json(result.rows);
  } 
  catch (err) {
    console.error(err);
    res.status(500).json({message: 'Unable to fetch playlist'});
  }
});
//deleting saved songs from frontend
router.delete('/playlist/:id', async (req, res) => {
  const {id} = req.params;

  try {
    await db.query('DELETE FROM playlist WHERE id = $1', [id]);
    res.json({message: 'Song removed'});
  } 
  catch (err) {
    console.error(err);
    res.status(500).json({message: 'Unable to delete song'});
  }
});

export default router;