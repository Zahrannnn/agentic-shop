import { configureStore } from "@reduxjs/toolkit";
import { preferencesSlice } from "./preferences-slice";

export const store = configureStore({
  reducer: {
    preferences: preferencesSlice.reducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
