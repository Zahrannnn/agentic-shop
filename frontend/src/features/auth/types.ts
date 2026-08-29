export type AuthUser = {
  id: string;
  name: string;
  email: string;
};

export type Session = {
  user: AuthUser;
};

export type LoginInput = {
  email: string;
};
