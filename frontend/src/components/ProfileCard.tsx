import type { LearnerProfile } from '../types';

interface Props {
  profile: LearnerProfile;
}

export function ProfileCard({ profile }: Props) {
  return (
    <div className="profile-card">
      <p className="profile-card__name">{profile.name}</p>
      <p className="profile-card__row">{profile.village}</p>
      <p className="profile-card__row">{profile.interest}</p>
      {profile.notes && <p className="profile-card__notes">{profile.notes}</p>}
    </div>
  );
}
