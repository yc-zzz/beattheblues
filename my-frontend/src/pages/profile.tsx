import React from 'react';
import './profile.css';

const Profile = () => {
  const username = localStorage.getItem('username');

  return (
    <div>
      <h2>Welcome, {username ? username : 'Guest'}!</h2>
      {username ? 
      (<p>
        This is your profile page.
        </p>) : 
      (<p>Please log in to view your profile.</p>)}
      <a href="/" className="home-link">Return to Home</a>
    </div>
  );
};

export default Profile;
