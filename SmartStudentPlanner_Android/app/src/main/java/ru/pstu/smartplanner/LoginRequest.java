package ru.pstu.smartplanner;

public class LoginRequest {
    public String identifier;
    public String password;

    public LoginRequest(String identifier, String password) {
        this.identifier = identifier;
        this.password = password;
    }
}