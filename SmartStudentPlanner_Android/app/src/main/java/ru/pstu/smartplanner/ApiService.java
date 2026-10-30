package ru.pstu.smartplanner;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.Header;
import retrofit2.http.POST;

public interface ApiService {
    @POST("api/v1/auth/register")
    Call<UserResponse> register(@Body RegisterRequest request);

    @POST("api/v1/auth/login")
    Call<TokenResponse> login(@Body LoginRequest request);

    @GET("api/v1/users/me")
    Call<UserResponse> getMe(@Header("Authorization") String bearerToken);
}