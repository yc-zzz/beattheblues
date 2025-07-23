import express from 'express';
import db from '../db.js';

const router = express.Router();

router.get('/random', async(req,res) => {
    try{
        const result = await db.query( //sort by random and take the first row
            `SELECT name, artist
            FROM acousticbrainz_data
            ORDER BY RANDOM() 
            LIMIT 1`
        );

        const {name, artist} = result.rows[0];
        const recommendation  = `${name} by ${artist}`;
        res.json({recommendation});
    } catch (e){
        console.error(e);
        res.status(500).json({message: 'error fetching song'});
    }
})

export default router;