import { configureStore } from "@reduxjs/toolkit";
import {
  persistSessionMiddleware,
  sessionSlice,
} from "@/features/shopping/store/session-slice";
import { transcriptSlice } from "@/features/shopping/store/transcript-slice";
import { preferencesSlice } from "./preferences-slice";

export const store = configureStore({
  reducer: {
    preferences: preferencesSlice.reducer,
    agentSession: sessionSlice.reducer,
    agentTranscript: transcriptSlice.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(persistSessionMiddleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
