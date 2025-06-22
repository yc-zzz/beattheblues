import React from 'react';

const Profile = () => {
  const username = localStorage.getItem('username');

  return (
    <div>
      <h2>Welcome, {username ? username : 'Guest'}!</h2>
      {username ? (<p>This is your profile page.</p>) : 
      (<p>Please log in to view your profile.</p>)}
    </div>
  );
};

export default Profile;
